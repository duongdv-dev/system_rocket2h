import os
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from feature_extractor import FeatureExtractor

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
    features_df, raw_m1_df = extractor.extract_daily_features()
    print(f"Trích xuất thành công {len(features_df)} ngày dữ liệu huấn luyện.")

    # Gán nhãn Bad Day (Các ngày có biến động lớn nguy cơ thua lỗ DCA)
    # Lọc dựa trên directional_intensity > 0.65 và range_to_atr_ratio > 2.2 hoặc morning_vol_std > 2.5
    features_df['is_bad_day'] = (
        (features_df['directional_intensity'] >= 0.62) & (features_df['range_to_atr_ratio'] >= 1.8)
    ) | (features_df['morning_vol_std'] >= 2.5) | (features_df['atr_ratio_20d'] >= 1.6)

    features_df['is_bad_day'] = features_df['is_bad_day'].astype(int)

    bad_count = features_df['is_bad_day'].sum()
    good_count = len(features_df) - bad_count
    print(f"Phân bổ nhãn: Safe Days = {good_count} | High Risk Bad Days = {bad_count}")

    feature_cols = [
        "atr14_m5", "atr_ratio_20d", "morning_range_pts", "morning_trend_pts",
        "directional_intensity", "range_to_atr_ratio", "trend_to_atr_ratio",
        "morning_vol_std", "open_daily_dist", "range_30m", "day_of_week"
    ]

    X = features_df[feature_cols]
    y = features_df['is_bad_day']

    clf = RandomForestClassifier(n_estimators=300, max_depth=5, random_state=42)
    clf.fit(X, y)

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
        "train_days_count": len(features_df),
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
