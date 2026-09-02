import os
import sys
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from feature_extractor import FeatureExtractor
from single_trade_backtester import SingleTradeBacktester

def train_ai_model_2020_2023(k_multiplier=1.2):
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
        raise FileNotFoundError("Không tìm thấy các file CSV 2020-2023 để huấn luyện AI!")

    print("\n==================================================================================")
    print("  🧠 SINGLE-TRADE SYSTEM: TRAINING AI RISK FILTER (DỮ LIỆU 2020 - 2023)")
    print("==================================================================================")

    extractor = FeatureExtractor(train_files)
    features_df, _ = extractor.extract_daily_features()

    bt = SingleTradeBacktester(train_files)
    unfiltered_logs, baseline_final_bal = bt.run_backtest(k_multiplier=k_multiplier)
    df_logs = pd.DataFrame(unfiltered_logs)

    cols_to_drop = [c for c in ['anchor_price_10am', 'atr14_m5'] if c in df_logs.columns]
    df_logs_clean = df_logs.drop(columns=cols_to_drop, errors='ignore')

    df_dataset = pd.merge(features_df, df_logs_clean, on='date')

    # Label days: Skip if trade was opened and closed negative (daily_pnl_usd < -5.0 USD)
    df_dataset['label'] = np.where((df_dataset['position_opened'] == True) & (df_dataset['daily_pnl_usd'] < -5.0), 'skip', 'trade')
    df_dataset['target'] = (df_dataset['label'] == 'skip').astype(int)

    # Sample weights: Higher weight for severe loss days
    sample_weights = np.where(df_dataset['daily_pnl_usd'] < -100.0, 10.0, np.where(df_dataset['label'] == 'skip', 3.0, 1.0))
    skip_count = (df_dataset['label'] == 'skip').sum()
    trade_count = (df_dataset['label'] == 'trade').sum()

    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

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

    if len(ai_model.classes_) > 1:
        if 1 in ai_model.classes_:
            class_1_idx = list(ai_model.classes_).index(1)
            y_probs = ai_model.predict_proba(X_train)[:, class_1_idx]
        else:
            y_probs = np.zeros(len(X_train))
    else:
        y_probs = np.zeros(len(X_train))

    if len(np.unique(y_train)) > 1:
        auc_score = float(roc_auc_score(y_train, y_probs))
    else:
        auc_score = 1.0

    importances = ai_model.feature_importances_
    feat_imp = {col: round(float(imp), 4) for col, imp in zip(feature_cols, importances)}

    risk_thresh = 0.38
    model_file = os.path.join(output_dir, "ai_single_risk_model.joblib")
    meta_file = os.path.join(output_dir, "ai_single_model_meta.json")

    joblib.dump({
        "model": ai_model,
        "feature_cols": feature_cols,
        "risk_threshold": risk_thresh
    }, model_file)

    meta_info = {
        "model_type": "RandomForestClassifier (Single-Trade Risk Filter)",
        "n_estimators": 300,
        "max_depth": 5,
        "train_period": "2020 - 2023",
        "train_days_count": len(df_dataset),
        "total_bad_days_in_train": int(skip_count),
        "total_good_days_in_train": int(trade_count),
        "auc_roc_score": round(auc_score, 4),
        "selected_risk_threshold": risk_thresh,
        "feature_importances": feat_imp
    }

    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta_info, f, indent=4, ensure_ascii=False)

    print(f"✅ Training hoàn tất cho Single-Trade System!")
    print(f"   - Mô hình lưu tại: {model_file}")
    print(f"   - ROC-AUC Score: {auc_score:.4f}")
    print(f"   - Risk Threshold: {risk_thresh}")
    print("==================================================================================\n")

    return ai_model, meta_info

if __name__ == "__main__":
    train_ai_model_2020_2023()
