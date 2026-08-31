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
from dca_backtester import DCABacktester

def run_step_1_training():
    """
    TRAINING MÔ HÌNH AI PHÂN TÍCH RỦI RO & DÙNG DỰ ĐOÁN XÁC SUẤT P(RISK) ĐỂ TỐI ƯU VOLUME
    """
    print("\n" + "=" * 80)
    print("   🤖 TRAINING MÔ HÌNH AI RISK PREDICTION CHO VOLUME OPTIMIZER (2020 - 2023)")
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

    extractor = FeatureExtractor(train_files)
    features_df, _ = extractor.extract_daily_features()

    bt_unfiltered = DCABacktester(train_files, max_daily_loss_pct=5.0)
    unfiltered_logs, baseline_final_bal = bt_unfiltered.run_backtest()
    df_logs = pd.DataFrame(unfiltered_logs)

    cols_to_drop = [c for c in ['anchor_price_10am', 'atr14_m5_step', 'atr14_m5'] if c in df_logs.columns]
    df_logs_clean = df_logs.drop(columns=cols_to_drop, errors='ignore')

    df_dataset = pd.merge(features_df, df_logs_clean, on='date')

    # Label target bad days
    df_dataset['label'] = np.where((df_dataset['daily_pnl_usd'] < -20.0) | (df_dataset['sl_hit'] == True), 'skip', 'trade')
    df_dataset['target'] = (df_dataset['label'] == 'skip').astype(int)

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

    best_thresh = 0.36
    model_file = os.path.join(output_dir, "ai_risk_model.joblib")
    meta_file = os.path.join(output_dir, "ai_model_meta.json")

    joblib.dump({
        "model": ai_model,
        "feature_cols": feature_cols,
        "risk_threshold": best_thresh
    }, model_file)

    meta_info = {
        "model_type": "RandomForestClassifier (Volume Optimizer Model)",
        "n_estimators": 300,
        "max_depth": 5,
        "train_period": "2020 - 2023",
        "train_days_count": len(df_dataset),
        "total_bad_days_in_train": int(skip_count),
        "total_safe_days_in_train": int(trade_count),
        "roc_auc_score": round(auc_score, 4),
        "feature_importances": feat_imp,
        "optimal_risk_threshold": best_thresh
    }

    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta_info, f, indent=4, ensure_ascii=False)

    print(f"✅ ĐÃ TẠO MÔ HÌNH AI VOLUME OPTIMIZER: {model_file}")
    return ai_model, meta_info

if __name__ == "__main__":
    run_step_1_training()
