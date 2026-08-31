import os
import sys
import json
import joblib
import pytz
import pandas as pd
import numpy as np

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(base_dir, "src"))
from dca_backtester import DCABacktester

class FilterBacktester(DCABacktester):
    def __init__(self, data_paths, ai_model_path=None, filter_rules=None, initial_balance=10000.0, default_lot=0.40, lot_usd_per_point=100.0, max_daily_loss_pct=20.0):
        super().__init__(data_paths, initial_balance, default_lot, lot_usd_per_point, max_daily_loss_pct)
        self.ai_model_data = None
        self.filter_rules = filter_rules

        if ai_model_path and os.path.exists(ai_model_path):
            self.ai_model_data = joblib.load(ai_model_path)
        else:
            default_model_p = os.path.join(base_dir, "output", "ai_risk_model.joblib")
            if os.path.exists(default_model_p):
                self.ai_model_data = joblib.load(default_model_p)

    def evaluate_filter_decision(self, feature_row):
        if self.ai_model_data:
            model = self.ai_model_data["model"]
            feature_cols = self.ai_model_data["feature_cols"]
            threshold = self.ai_model_data["risk_threshold"]

            feat_vals = [float(feature_row[c]) for c in feature_cols]
            X_input = pd.DataFrame([feat_vals], columns=feature_cols)
            
            prob_risk = float(model.predict_proba(X_input)[0][1])

            if prob_risk >= threshold:
                return False, f"Mô hình AI cảnh báo Rủi Ro Cao (P={prob_risk*100:.1f}% ≥ {threshold*100:.1f}%)"
                
            return True, f"AI xác nhận An Toàn (P={prob_risk*100:.1f}% < {threshold*100:.1f}%)"

        return True, "Passed Default Filter"
