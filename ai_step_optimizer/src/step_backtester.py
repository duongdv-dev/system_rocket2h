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
from step_optimizer import StepOptimizer

class StepBacktester(DCABacktester):
    def __init__(self, data_paths, ai_model_path=None, initial_balance=10000.0, default_lot=1.20, max_daily_loss_pct=30.0):
        super().__init__(data_paths, initial_balance, default_lot, lot_usd_per_point=100.0, max_daily_loss_pct=max_daily_loss_pct)
        self.ai_model_data = None
        self.step_optimizer = StepOptimizer(base_lot=default_lot, min_lot=0.50, safe_step_mult=0.50, moderate_step_mult=0.85)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if ai_model_path and os.path.exists(ai_model_path):
            self.ai_model_data = joblib.load(ai_model_path)
        else:
            default_model_p = os.path.join(base_dir, "output", "ai_risk_model.joblib")
            if os.path.exists(default_model_p):
                self.ai_model_data = joblib.load(default_model_p)

    def calculate_master_daily_configs(self, features_df):
        config_map = {}

        if not self.ai_model_data:
            for _, row in features_df.iterrows():
                config_map[row['date']] = {'lot': self.default_lot, 'step_mult': 1.0, 'reason': 'Chưa nạp AI Model'}
            return config_map

        model = self.ai_model_data["model"]
        feature_cols = self.ai_model_data["feature_cols"]
        skip_threshold = self.ai_model_data["risk_threshold"]

        for _, row in features_df.iterrows():
            date_str = row['date']
            feat_vals = [float(row[c]) for c in feature_cols]
            X_input = pd.DataFrame([feat_vals], columns=feature_cols)
            
            prob_risk = float(model.predict_proba(X_input)[0][1])

            cfg = self.step_optimizer.compute_master_config(prob_risk, skip_threshold=skip_threshold, safe_threshold=0.20)
            config_map[date_str] = cfg

        return config_map
