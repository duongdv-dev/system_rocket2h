import os
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from feature_extractor import FeatureExtractor
from master_13step_backtester import Master13StepBacktester

def train_master_ai():
    print("=" * 70)
    print("🚀 HUẤN LUYỆN MÔ HÌNH AI MASTER 13 LỚP (TRAIN PERIOD: 2020 - 2023)")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = ["XAUUSD_2020_m1.csv", "XAUUSD_2021_m1.csv", "XAUUSD_2022_m1.csv", "XAUUSD_2023_m1.csv"]
    
    train_paths = []
    for f in files:
        possible_paths = [
            os.path.join(base_dir, f),
            os.path.join("/app/data", f),
            os.path.join("/app", f),
            os.path.join(".", f)
        ]
        found = False
        for p in possible_paths:
            if os.path.exists(p):
                train_paths.append(p)
                found = True
                break
        if not found:
            print(f"Warning: {f} not found in candidate locations.")

    extractor = FeatureExtractor(train_paths)
    features_df, _ = extractor.extract_daily_features()
    print(f"Trích xuất thành công {len(features_df)} ngày đặc trưng huấn luyện.")

    # 1. Backtest Baseline thô để gán nhãn chính xác theo PnL thực tế
    backtester_base = Master13StepBacktester(train_paths, model_path=None, default_lot=0.60)
    _, logs_base = backtester_base.run_13step_backtest(max_step=0)
    df_logs = pd.DataFrame(logs_base)

    cols_to_drop = [c for c in ['anchor_price_10am', 'atr14_m5_raw', 'atr14_m5'] if c in df_logs.columns]
    df_logs_clean = df_logs.drop(columns=cols_to_drop, errors='ignore')

    df_dataset = pd.merge(features_df, df_logs_clean, on='date')

    # Gán nhãn Bad Day: PnL < -$20 hoặc bị SL Hit
    df_dataset['target'] = np.where((df_dataset['daily_pnl_usd'] < -20.0) | (df_dataset['sl_hit'] == True), 1, 0)
    sample_weights = np.where(df_dataset['sl_hit'] == True, 30.0, 1.0)

    bad_count = df_dataset['target'].sum()
    good_count = len(df_dataset) - bad_count
    print(f"Phân bổ nhãn huấn luyện: Safe Days = {good_count} | High Risk Bad Days = {bad_count}")

    feature_cols = [
        "atr14_m5", "atr_ratio_20d", "morning_range_pts", "morning_trend_pts",
        "directional_intensity", "range_to_atr_ratio", "trend_to_atr_ratio",
        "morning_vol_std", "open_daily_dist", "range_30m", "day_of_week"
    ]

    X = df_dataset[feature_cols]
    y = df_dataset['target']

    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42
    )
    clf.fit(X, y, sample_weight=sample_weights)

    y_pred_prob = clf.predict_proba(X)[:, 1]
    auc_score = roc_auc_score(y, y_pred_prob)
    print(f"🏆 AI Model ROC-AUC Score: {auc_score:.4f}")

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, "ai_master_model.joblib")
    joblib.dump(clf, model_path)
    print(f"Saved AI Model to: {model_path}")

    importances = dict(zip(feature_cols, [round(f, 4) for f in clf.feature_importances_]))

    meta = {
        "model_type": "RandomForestClassifier (Master 13-Step Model)",
        "n_estimators": 300,
        "max_depth": 5,
        "train_period": "2020 - 2023",
        "train_days_count": len(df_dataset),
        "total_bad_days_in_train": int(bad_count),
        "total_safe_days_in_train": int(good_count),
        "roc_auc_score": round(auc_score, 4),
        "feature_importances": importances,
        "optimal_risk_threshold": 0.36
    }

    meta_path = os.path.join(output_dir, "ai_model_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=4)

    print(f"Saved Model Meta to: {meta_path}")

if __name__ == "__main__":
    train_master_ai()
