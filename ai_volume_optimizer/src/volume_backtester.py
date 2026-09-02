import os
import sys
import json
import joblib
import pandas as pd
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from dca_backtester import DCABacktester
from volume_optimizer import VolumeOptimizer

class VolumeBacktester(DCABacktester):
    def __init__(self, data_paths, ai_model_path=None, initial_balance=10000.0, default_lot=0.60, max_daily_loss_pct=20.0):
        super().__init__(data_paths, initial_balance, default_lot, lot_usd_per_point=100.0, max_daily_loss_pct=max_daily_loss_pct)
        self.ai_model_data = None
        self.vol_optimizer = VolumeOptimizer(base_lot=default_lot, min_lot=0.12, max_lot=default_lot)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if ai_model_path and os.path.exists(ai_model_path):
            self.ai_model_data = joblib.load(ai_model_path)
        else:
            default_model_p = os.path.join(base_dir, "output", "ai_risk_model.joblib")
            if os.path.exists(default_model_p):
                self.ai_model_data = joblib.load(default_model_p)

    def calculate_daily_dynamic_volumes(self, features_df):
        volume_map = {}
        decision_reasons = {}

        if not self.ai_model_data:
            for _, row in features_df.iterrows():
                volume_map[row['date']] = self.default_lot
                decision_reasons[row['date']] = f"Cố định {self.default_lot} Lot"
            return volume_map, decision_reasons

        model = self.ai_model_data["model"]
        feature_cols = self.ai_model_data["feature_cols"]
        skip_threshold = self.ai_model_data["risk_threshold"]

        for _, row in features_df.iterrows():
            date_str = row['date']
            feat_vals = [float(row[c]) for c in feature_cols]
            X_input = pd.DataFrame([feat_vals], columns=feature_cols)
            
            probs = model.predict_proba(X_input)[0]
            if len(model.classes_) > 1 and 1 in model.classes_:
                class_1_idx = list(model.classes_).index(1)
                prob_risk = float(probs[class_1_idx])
            else:
                prob_risk = 1.0 if model.classes_[0] == 1 else 0.0

            active_lot = self.vol_optimizer.compute_bucket_lot(prob_risk, skip_threshold=skip_threshold, safe_threshold=0.20)
            volume_map[date_str] = active_lot

            if active_lot == 0.00:
                decision_reasons[date_str] = f"🛑 AI BỎ QUA (SKIP): P={prob_risk*100:.1f}% ≥ {skip_threshold*100:.1f}%"
            elif active_lot < self.default_lot:
                decision_reasons[date_str] = f"⚠️ GIẢM VOLUME xuống {active_lot} Lot: P={prob_risk*100:.1f}%"
            else:
                decision_reasons[date_str] = f"✅ GIỮ NGUYÊN {active_lot} Lot: P={prob_risk*100:.1f}% An Toàn"

        return volume_map, decision_reasons
