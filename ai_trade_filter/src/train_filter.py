import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from feature_extractor import FeatureExtractor
from filter_backtester import FilterBacktester

def run_step_1_training():
    """
    BƯỚC 1: TRAINING MÔ HÌNH AI VỚI NGƯỠNG NHẠY CẢM RỦI RO CAO (TARGET 5% SL DAYS)
    - Tối ưu hóa Risk Threshold P >= 0.38 - 0.40 để CHẶN ĐỨNG TRIỆT ĐỂ 100% CÁC NGÀY DÍNH CẮT LỖ 5%.
    - Phạt x30 cho các ngày dính Cắt Lỗ 5%.
    """
    print("\n" + "=" * 80)
    print("   🤖 TRAINING MÔ HÌNH AI - SIẾT NẶNG NGƯỠNG NHẠY CẢM CHẶN 100% NGÀY SL 5%")
    print("=" * 80)

    src_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(src_dir)
    workspace_dir = os.path.dirname(base_dir)

    possible_path_sets = [
        [
            os.path.join(workspace_dir, "XAUUSD_2020_m1.csv"),
            os.path.join(workspace_dir, "XAUUSD_2021_m1.csv"),
            os.path.join(workspace_dir, "XAUUSD_2022_m1.csv"),
            os.path.join(workspace_dir, "XAUUSD_2023_m1.csv")
        ],
        [
            os.path.join(base_dir, "..", "XAUUSD_2020_m1.csv"),
            os.path.join(base_dir, "..", "XAUUSD_2021_m1.csv"),
            os.path.join(base_dir, "..", "XAUUSD_2022_m1.csv"),
            os.path.join(base_dir, "..", "XAUUSD_2023_m1.csv")
        ],
        [
            "/app/data/XAUUSD_2020_m1.csv",
            "/app/data/XAUUSD_2021_m1.csv",
            "/app/data/XAUUSD_2022_m1.csv",
            "/app/data/XAUUSD_2023_m1.csv"
        ]
    ]

    train_files = None
    for path_set in possible_path_sets:
        if all(os.path.exists(p) for p in path_set):
            train_files = path_set
            break

    if not train_files:
        raise FileNotFoundError("Không tìm thấy các file CSV 2020-2023!")

    # 1. Trích xuất chỉ số 10:00 sáng ICT
    extractor = FeatureExtractor(train_files)
    features_df, _ = extractor.extract_daily_features()

    # 2. Chạy mô phỏng DCA thô với Cap 5.0%
    bt_unfiltered = FilterBacktester(train_files, ai_model_path=None, filter_rules=None, max_daily_loss_pct=5.0)
    unfiltered_logs, baseline_final_bal = bt_unfiltered.run_backtest()
    df_logs = pd.DataFrame(unfiltered_logs)

    cols_to_drop = [c for c in ['anchor_price_10am', 'atr14_m5_step', 'atr14_m5'] if c in df_logs.columns]
    df_logs_clean = df_logs.drop(columns=cols_to_drop, errors='ignore')

    df_dataset = pd.merge(features_df, df_logs_clean, on='date')

    # ĐÁNH NHÃN 'skip' NẾU LỖ PnL < -20.0 HOẶC DÍNH SL 5%
    df_dataset['label'] = np.where((df_dataset['daily_pnl_usd'] < -20.0) | (df_dataset['sl_hit'] == True), 'skip', 'trade')
    df_dataset['target'] = (df_dataset['label'] == 'skip').astype(int)

    # Trọng số phạt đặc biệt x30.0 cho ngày dính Cắt Lỗ SL 5%
    sample_weights = np.where(df_dataset['sl_hit'] == True, 30.0, 1.0)

    skip_count = (df_dataset['label'] == 'skip').sum()
    trade_count = (df_dataset['label'] == 'trade').sum()

    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    csv_output_path = os.path.join(output_dir, "labeled_training_days_2020_2023.csv")
    json_output_path = os.path.join(output_dir, "labeled_training_days_2020_2023.json")

    export_cols = [
        'date', 'label', 'daily_pnl_usd', 'tp_hit', 'sl_hit', 'trades_count',
        'anchor_price_10am', 'atr14_m5', 'atr_ratio_20d', 'morning_range_pts',
        'morning_trend_pts', 'directional_intensity', 'range_to_atr_ratio', 'trend_to_atr_ratio', 'morning_vol_std', 'day_of_week'
    ]
    df_dataset[export_cols].to_csv(csv_output_path, index=False)
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(df_dataset[export_cols].to_dict(orient='records'), f, indent=4, ensure_ascii=False)

    # 3. Huấn luyện RandomForestClassifier
    feature_cols = [
        'atr_ratio_20d', 'directional_intensity', 'range_to_atr_ratio', 
        'trend_to_atr_ratio', 'morning_vol_std', 'day_of_week'
    ]
    
    X_train = df_dataset[feature_cols]
    y_train = df_dataset['target']

    ai_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42
    )
    ai_model.fit(X_train, y_train, sample_weight=sample_weights)

    y_probs = ai_model.predict_proba(X_train)[:, 1]
    auc_score = roc_auc_score(y_train, y_probs)

    importances = ai_model.feature_importances_
    feat_imp = {col: round(float(imp), 4) for col, imp in zip(feature_cols, importances)}

    # Tối ưu hóa Ngưỡng Risk Threshold Siết Nhạy Cảm (P >= 0.38)
    best_thresh = 0.38
    best_score = -999999.0
    best_stats = {}

    for thresh in np.arange(0.32, 0.46, 0.01):
        filt_bal = 10000.0
        peak_bal = 10000.0
        max_dd = 0.0
        skipped_bad = 0
        skipped_good = 0
        sl_skipped = 0

        for idx, row in df_dataset.iterrows():
            prob_risk = y_probs[idx]
            if prob_risk < thresh:
                pnl = row['daily_pnl_usd']
                filt_bal += pnl
                if filt_bal > peak_bal:
                    peak_bal = filt_bal
                dd = peak_bal - filt_bal
                if dd > max_dd:
                    max_dd = dd
            else:
                if row['target'] == 1:
                    skipped_bad += 1
                    if row['sl_hit'] == True:
                        sl_skipped += 1
                else:
                    skipped_good += 1

        net_pnl = filt_bal - 10000.0
        # Score priority: Cực kỳ ưu tiên chặn ngày SL 5%
        score = net_pnl + (sl_skipped * 3000.0) - (skipped_good * 15.0)

        if score > best_score:
            best_score = score
            best_thresh = round(float(thresh), 2)
            best_stats = {
                "train_baseline_pnl": round(baseline_final_bal - 10000.0, 2),
                "train_filtered_pnl": round(net_pnl, 2),
                "train_max_dd": round(max_dd, 2),
                "bad_days_skipped": skipped_bad,
                "good_days_skipped": skipped_good,
                "sl_days_skipped": sl_skipped
            }

    # 4. Lưu Model Artifacts
    model_file = os.path.join(output_dir, "ai_risk_model.joblib")
    meta_file = os.path.join(output_dir, "ai_model_meta.json")

    joblib.dump({
        "model": ai_model,
        "feature_cols": feature_cols,
        "risk_threshold": best_thresh
    }, model_file)

    meta_info = {
        "model_type": "RandomForestClassifier (High-Sensitivity 5% SL Targeted)",
        "n_estimators": 300,
        "max_depth": 5,
        "train_period": "2020 - 2023",
        "train_days_count": len(df_dataset),
        "total_bad_days_in_train": int(skip_count),
        "total_safe_days_in_train": int(trade_count),
        "roc_auc_score": round(auc_score, 4),
        "feature_importances": feat_imp,
        "optimal_risk_threshold": best_thresh,
        "training_performance": best_stats
    }

    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta_info, f, indent=4, ensure_ascii=False)

    print("\n================ TỔNG KẾT TRAINING SIẾT NGƯỠNG NHẠY CẢM SL 5% ================")
    print(f"✅ Mô Hình AI Trained       : RandomForestClassifier (5% SL Target)")
    print(f"✅ Ngưỡng Cảnh Báo Siết Nặng: P(skip) >= {best_thresh}")
    print(f"✅ Đánh Giá ROC-AUC Score   : {auc_score:.4f}")
    print(f"✅ Số Ngày SL 5% Chặn Được : {best_stats.get('sl_days_skipped', 0)} ngày")
    print(f"✅ File Model AI Lưu Tại   : {model_file}")
    print("===============================================================================\n")

    return ai_model, meta_info

if __name__ == "__main__":
    run_step_1_training()
