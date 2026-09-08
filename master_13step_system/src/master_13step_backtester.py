import os
import json
import joblib
import pytz
import pandas as pd
import numpy as np
from datetime import datetime, time
from feature_extractor import FeatureExtractor
from master_engine import Master13StepEngine

class Master13StepBacktester:
    """
    Động Cơ Backtest Thời Gian Thực 13 Bước AI (10:00 - 12:00 ICT):
    Hỗ trợ tham số max_step (0 đến 13) để kiểm chứng từng bước phát triển.
    """
    def __init__(self, data_paths, model_path=None, initial_balance=10000.0, default_lot=0.60, lot_usd_per_point=100.0, max_daily_loss_pct=20.0):
        self.data_paths = data_paths
        self.initial_balance = initial_balance
        self.default_lot = default_lot
        self.lot_usd_per_point = lot_usd_per_point
        self.max_daily_loss_pct = max_daily_loss_pct
        self.tz_ict = pytz.timezone("Asia/Ho_Chi_Minh")

        if model_path and os.path.exists(model_path):
            self.model = joblib.load(model_path)
        else:
            self.model = None

        self.engine = Master13StepEngine(base_lot=default_lot)

    def run_13step_backtest(self, max_step=13):
        extractor = FeatureExtractor(self.data_paths)
        features_df, raw_m1_df = extractor.extract_daily_features()

        feature_cols = [
            "atr14_m5", "atr_ratio_20d", "morning_range_pts", "morning_trend_pts",
            "directional_intensity", "range_to_atr_ratio", "trend_to_atr_ratio",
            "morning_vol_std", "open_daily_dist", "range_30m", "day_of_week"
        ]

        trading_days = sorted(features_df['date'].unique())
        daily_logs = []
        cumulative_balance = self.initial_balance
        peak_equity = self.initial_balance

        skipped_days = 0
        trade_days = 0
        tp_days = 0
        sl_days = 0
        early_exit_days = 0

        for date_str in trading_days:
            feat_row = features_df[features_df['date'] == date_str].iloc[0]
            feat_dict = feat_row.to_dict()

            if self.model is not None and max_step >= 1:
                X_feat = pd.DataFrame([feat_row[feature_cols]])
                prob_risk = float(self.model.predict_proba(X_feat)[0, 1])
            else:
                prob_risk = 0.0 # Step 0: Risk = 0 so no skipping

            pre10_cfg = self.engine.compute_pre10_config(prob_risk, feat_dict, max_step=max_step)

            day_m1 = raw_m1_df[raw_m1_df['date_str'] == date_str].copy()
            target_10am = time(10, 0, 0)
            target_12pm = time(12, 0, 0)

            window_session = day_m1[(day_m1['time'] >= target_10am) & (day_m1['time'] <= target_12pm)].copy()
            if window_session.empty or pre10_cfg["decision"] == "SKIP":
                skipped_days += 1
                daily_logs.append({
                    "date": date_str,
                    "anchor_price_10am": feat_dict["anchor_price_10am"],
                    "atr14_m5_raw": feat_dict["atr14_m5"],
                    "prob_risk_pct": round(prob_risk * 100, 1),
                    "decision": "SKIP",
                    "active_lot_size": 0.0,
                    "direction": "NONE",
                    "trades_count": 0,
                    "tp_hit": False,
                    "sl_hit": False,
                    "early_exit": False,
                    "daily_pnl_usd": 0.0,
                    "ending_equity_usd": round(cumulative_balance, 2),
                    "reason": pre10_cfg["reason"]
                })
                continue

            trade_days += 1
            bar_10am = window_session.iloc[0]
            anchor_price = float(bar_10am['open'])
            raw_atr = feat_dict["atr14_m5"]

            active_lot = pre10_cfg["active_lot"]
            entry_step_buy = raw_atr * pre10_cfg["entry_factor_buy"]
            entry_step_sell = raw_atr * pre10_cfg["entry_factor_sell"]
            dca_step_buy = raw_atr * pre10_cfg["dca_factor_buy"]
            dca_step_sell = raw_atr * pre10_cfg["dca_factor_sell"]

            direction = "NONE"
            positions = []
            max_level = 0
            tp_hit = False
            sl_hit = False
            early_exit = False
            session_closed = False
            daily_pnl = 0.0

            start_day_equity = cumulative_balance
            max_allowed_loss_usd = start_day_equity * (self.max_daily_loss_pct / 100.0)
            usd_per_point = active_lot * self.lot_usd_per_point

            allow_dca = True
            tp_target_price = anchor_price

            for idx, bar in window_session.iterrows():
                if session_closed:
                    break

                b_high = float(bar['high'])
                b_low = float(bar['low'])
                b_close = float(bar['close'])
                b_time = bar['time']

                # 1. KÍCH HOẠT VỊ THẾ BAN ĐẦU
                if direction == "NONE":
                    buy_trigger = b_low <= (anchor_price - entry_step_buy)
                    sell_trigger = b_high >= (anchor_price + entry_step_sell)

                    if buy_trigger and not sell_trigger:
                        direction = "BUY"
                    elif sell_trigger and not buy_trigger:
                        direction = "SELL"
                    elif buy_trigger and sell_trigger:
                        buy_dist = anchor_price - b_low
                        sell_dist = b_high - anchor_price
                        direction = "BUY" if buy_dist >= sell_dist else "SELL"

                # 2. XỬ LÝ VỊ THẾ TRONG PHIÊN
                if direction == "BUY":
                    if allow_dca:
                        curr_max_k = int(np.floor((anchor_price - b_low) / dca_step_buy))
                        if curr_max_k > max_level:
                            for k in range(max_level + 1, curr_max_k + 1):
                                entry_p = anchor_price - k * dca_step_buy
                                positions.append({'level': k, 'entry_price': entry_p, 'lot': active_lot})
                            max_level = curr_max_k

                    if positions:
                        floating_pnl = sum((b_close - pos['entry_price']) * usd_per_point for pos in positions)

                        chk_action = self.engine.evaluate_in_session_checkpoints(
                            b_time, direction, positions, b_close, anchor_price, raw_atr, floating_pnl, max_allowed_loss_usd, max_step=max_step
                        )

                        allow_dca = chk_action["allow_dca"]
                        tp_target_price = chk_action["tp_target_price"]

                        if chk_action["early_exit"]:
                            daily_pnl = floating_pnl
                            early_exit = True
                            early_exit_days += 1
                            session_closed = True
                            break

                        if abs(floating_pnl) >= max_allowed_loss_usd and floating_pnl < 0:
                            daily_pnl = -max_allowed_loss_usd
                            sl_hit = True
                            sl_days += 1
                            session_closed = True
                            break

                        if b_high >= tp_target_price:
                            daily_pnl = sum((tp_target_price - pos['entry_price']) * usd_per_point for pos in positions)
                            tp_hit = True
                            tp_days += 1
                            session_closed = True
                            break

                elif direction == "SELL":
                    if allow_dca:
                        curr_max_k = int(np.floor((b_high - anchor_price) / dca_step_sell))
                        if curr_max_k > max_level:
                            for k in range(max_level + 1, curr_max_k + 1):
                                entry_p = anchor_price + k * dca_step_sell
                                positions.append({'level': k, 'entry_price': entry_p, 'lot': active_lot})
                            max_level = curr_max_k

                    if positions:
                        floating_pnl = sum((pos['entry_price'] - b_close) * usd_per_point for pos in positions)

                        chk_action = self.engine.evaluate_in_session_checkpoints(
                            b_time, direction, positions, b_close, anchor_price, raw_atr, floating_pnl, max_allowed_loss_usd, max_step=max_step
                        )

                        allow_dca = chk_action["allow_dca"]
                        tp_target_price = chk_action["tp_target_price"]

                        if chk_action["early_exit"]:
                            daily_pnl = floating_pnl
                            early_exit = True
                            early_exit_days += 1
                            session_closed = True
                            break

                        if abs(floating_pnl) >= max_allowed_loss_usd and floating_pnl < 0:
                            daily_pnl = -max_allowed_loss_usd
                            sl_hit = True
                            sl_days += 1
                            session_closed = True
                            break

                        if b_low <= tp_target_price:
                            daily_pnl = sum((pos['entry_price'] - tp_target_price) * usd_per_point for pos in positions)
                            tp_hit = True
                            tp_days += 1
                            session_closed = True
                            break

            if not session_closed:
                last_bar = window_session.iloc[-1]
                exit_price = float(last_bar['close'])

                if direction == "BUY" and positions:
                    daily_pnl = sum((exit_price - pos['entry_price']) * usd_per_point for pos in positions)
                elif direction == "SELL" and positions:
                    daily_pnl = sum((pos['entry_price'] - exit_price) * usd_per_point for pos in positions)
                else:
                    daily_pnl = 0.0

            cumulative_balance += daily_pnl
            if cumulative_balance > peak_equity:
                peak_equity = cumulative_balance

            daily_logs.append({
                "date": date_str,
                "anchor_price_10am": round(anchor_price, 3),
                "atr14_m5_raw": round(raw_atr, 3),
                "prob_risk_pct": round(prob_risk * 100, 1),
                "decision": pre10_cfg["decision"],
                "active_lot_size": active_lot,
                "direction": direction,
                "trades_count": len(positions),
                "tp_hit": tp_hit,
                "sl_hit": sl_hit,
                "early_exit": early_exit,
                "daily_pnl_usd": round(daily_pnl, 2),
                "ending_equity_usd": round(cumulative_balance, 2),
                "reason": pre10_cfg["reason"]
            })

        summary = {
            "step": max_step,
            "initial_capital": self.initial_balance,
            "final_equity": round(cumulative_balance, 2),
            "net_pnl_usd": round(cumulative_balance - self.initial_balance, 2),
            "return_pct": round(((cumulative_balance - self.initial_balance) / self.initial_balance) * 100, 2),
            "total_trading_days": len(trading_days),
            "active_trade_days": trade_days,
            "skipped_days": skipped_days,
            "tp_days": tp_days,
            "sl_days": sl_days,
            "early_exit_days": early_exit_days,
            "win_rate_pct": round((tp_days / trade_days * 100) if trade_days > 0 else 0, 2)
        }

        return summary, daily_logs
