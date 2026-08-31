import os
import sys
import json
import joblib
import pytz
import pandas as pd
import numpy as np

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(base_dir, "..", "dca_system", "src"))
from dca_backtester import DCABacktester

class FilterBacktester(DCABacktester):
    def __init__(self, data_paths, ai_model_path=None, filter_rules=None, initial_balance=10000.0, default_lot=0.1, lot_usd_per_point=10.0, max_daily_loss_pct=10.0):
        super().__init__(data_paths, initial_balance, default_lot, lot_usd_per_point, max_daily_loss_pct)
        self.ai_model_data = None
        self.filter_rules = filter_rules

        # Load AI model if specified or if default output path exists
        if ai_model_path and os.path.exists(ai_model_path):
            self.ai_model_data = joblib.load(ai_model_path)
        else:
            default_model_p = os.path.join(base_dir, "output", "ai_risk_model.joblib")
            if os.path.exists(default_model_p):
                self.ai_model_data = joblib.load(default_model_p)

    def evaluate_filter_decision(self, feature_row):
        """
        Evaluate 10:00 AM decision using trained Machine Learning AI model or rules fallback.
        Returns (should_trade: bool, decision_reason: str)
        """
        # 1. Machine Learning Model Decision
        if self.ai_model_data:
            model = self.ai_model_data["model"]
            feature_cols = self.ai_model_data["feature_cols"]
            threshold = self.ai_model_data["risk_threshold"]

            # Safely extract feature vector X
            feat_vals = [float(feature_row[c]) for c in feature_cols]
            X_input = pd.DataFrame([feat_vals], columns=feature_cols)
            
            # Predict risk probability of Bad Day
            prob_risk = float(model.predict_proba(X_input)[0][1])

            if prob_risk >= threshold:
                return False, f"Mô hình AI cảnh báo Rủi Ro Cao (P={prob_risk*100:.1f}% ≥ {threshold*100:.1f}%)"
                
            return True, f"AI xác nhận An Toàn (P={prob_risk*100:.1f}% < {threshold*100:.1f}%)"

        # 2. Rule Fallback Decision
        if self.filter_rules:
            atr_ratio = feature_row.get('atr_ratio_20d', feature_row.get('atr_ratio', 1.0))
            morning_range = feature_row.get('morning_range_pts', feature_row.get('morning_range', 0.0))
            atr14 = feature_row['atr14_m5']

            max_atr_ratio = self.filter_rules.get("max_atr_ratio", 2.2)
            if atr_ratio > max_atr_ratio:
                return False, f"Biến động cao bất thường (ATR Ratio {atr_ratio:.2f} > {max_atr_ratio})"

            max_morning_range = self.filter_rules.get("max_morning_range", 18.0)
            if morning_range > max_morning_range:
                return False, f"Biên độ sáng quá lớn ({morning_range:.2f} > {max_morning_range} giá)"

            max_atr14 = self.filter_rules.get("max_atr14", 3.8)
            if atr14 > max_atr14:
                return False, f"ATR14 M5 quá lớn ({atr14:.2f} > {max_atr14})"

        return True, "Passed Default Filter"
