import os
import json
import pytz
import pandas as pd
import numpy as np
from datetime import datetime, time

class SingleTradeBacktester:
    def __init__(self, data_paths, initial_balance=10000.0, target_tp_pct=1.0, lot_usd_per_point=100.0, use_compounding=True):
        """
        Single-Trade 1% Target Profit Intraday Backtester XAUUSD (10:00 - 12:00 ICT Window)
        - Single Entry per day at P0 +/- (k * ATR)
        - Target Profit fixed at 1.0% Balance when price reverts to P0
        - Stop Loss / Exit condition: 12:00 PM ICT Time Cutoff
        """
        self.data_paths = data_paths
        self.initial_balance = initial_balance
        self.target_tp_pct = target_tp_pct  # 1.0%
        self.lot_usd_per_point = lot_usd_per_point
        self.use_compounding = use_compounding
        self.tz_ict = pytz.timezone("Asia/Ho_Chi_Minh")

    def load_and_preprocess_data(self):
        df_list = []
        for path in self.data_paths:
            if not os.path.exists(path):
                print(f"Warning: File not found at {path}")
                continue
            print(f"Loading data from: {os.path.basename(path)}")
            df = pd.read_csv(path)
            df_list.append(df)
            
        if not df_list:
            raise FileNotFoundError("No input data CSV files found!")
            
        full_df = pd.concat(df_list, ignore_index=True)
        full_df['dt_utc'] = pd.to_datetime(full_df['timestamp'], unit='ms', utc=True)
        full_df['dt_ict'] = full_df['dt_utc'].dt.tz_convert(self.tz_ict)
        full_df = full_df.sort_values('dt_ict').reset_index(drop=True)
        full_df['date_str'] = full_df['dt_ict'].dt.strftime('%Y-%m-%d')
        full_df['time'] = full_df['dt_ict'].dt.time
        return full_df

    def compute_m5_atr14(self, df):
        df_resample = df.set_index('dt_ict')
        m5_df = df_resample.resample('5min', closed='left', label='left').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        prev_close = m5_df['close'].shift(1)
        tr1 = m5_df['high'] - m5_df['low']
        tr2 = (m5_df['high'] - prev_close).abs()
        tr3 = (m5_df['low'] - prev_close).abs()
        m5_df['tr'] = np.maximum(tr1, np.maximum(tr2, tr3))
        m5_df['atr14'] = m5_df['tr'].rolling(window=14).mean()
        return m5_df

    def run_backtest(self, k_multiplier=1.5, daily_skip_dict=None):
        """
        Run backtest for Single Trade strategy.
        :param k_multiplier: Multiplier for entry distance D_entry = k * ATR14
        :param daily_skip_dict: Dict mapping date_str -> bool (True if AI flags SKIP day)
        """
        df = self.load_and_preprocess_data()
        m5_df = self.compute_m5_atr14(df)
        
        trading_days = sorted(df['date_str'].unique())

        daily_logs = []
        cumulative_balance = self.initial_balance
        peak_cumulative_equity = self.initial_balance

        for date_str in trading_days:
            day_m1 = df[df['date_str'] == date_str].copy()
            if day_m1.empty:
                continue

            target_10am = time(10, 0, 0)
            target_12pm = time(12, 0, 0)

            window_10_12 = day_m1[(day_m1['time'] >= target_10am) & (day_m1['time'] <= target_12pm)].copy()
            if window_10_12.empty:
                continue

            bar_10am = window_10_12.iloc[0]
            anchor_price = float(bar_10am['open'])
            anchor_dt = bar_10am['dt_ict']

            m5_prior = m5_df[m5_df.index <= anchor_dt]
            if len(m5_prior) == 0 or pd.isna(m5_prior['atr14'].iloc[-1]):
                raw_atr = 1.5
            else:
                raw_atr = float(m5_prior['atr14'].iloc[-1])

            raw_atr = max(raw_atr, 0.1)

            start_day_equity = cumulative_balance
            
            # Check AI Risk Filter SKIP
            is_skipped = False
            if daily_skip_dict and date_str in daily_skip_dict:
                is_skipped = bool(daily_skip_dict[date_str])

            if is_skipped:
                daily_logs.append({
                    "date": date_str,
                    "anchor_price_10am": round(anchor_price, 3),
                    "atr14_m5": round(raw_atr, 3),
                    "k_multiplier": k_multiplier,
                    "entry_distance_pts": round(k_multiplier * raw_atr, 3),
                    "active_lot_size": 0.0,
                    "direction": "SKIP",
                    "position_opened": False,
                    "tp_hit": False,
                    "cutoff_hit": False,
                    "daily_pnl_usd": 0.0,
                    "daily_pnl_pct": 0.0,
                    "ending_equity_usd": round(cumulative_balance, 2),
                    "max_drawdown_usd": 0.0,
                    "max_drawdown_pct": 0.0
                })
                continue

            # Calculate Entry Distance D_entry
            d_entry = max(k_multiplier * raw_atr, 0.2)

            # Calculate Lot Size for Target TP Profit = 1% Balance at P0
            # Profit = Lot * d_entry * 100 = start_day_equity * (target_tp_pct / 100)
            target_profit_usd = start_day_equity * (self.target_tp_pct / 100.0)
            raw_lot = target_profit_usd / (d_entry * self.lot_usd_per_point)
            active_lot = round(float(np.floor(raw_lot * 100.0) / 100.0), 2)
            active_lot = max(active_lot, 0.01)

            usd_per_point = active_lot * self.lot_usd_per_point

            direction = "NONE"
            entry_price = 0.0
            position_opened = False
            tp_hit = False
            cutoff_hit = False
            daily_pnl = 0.0
            max_drawdown_usd = 0.0

            # Single Pending Limit Order triggers
            buy_limit_p = anchor_price - d_entry
            sell_limit_p = anchor_price + d_entry

            for idx, bar in window_10_12.iterrows():
                b_high = float(bar['high'])
                b_low = float(bar['low'])
                b_close = float(bar['close'])

                if not position_opened:
                    buy_trigger = b_low <= buy_limit_p
                    sell_trigger = b_high >= sell_limit_p

                    if buy_trigger and not sell_trigger:
                        direction = "BUY"
                        entry_price = buy_limit_p
                        position_opened = True
                    elif sell_trigger and not buy_trigger:
                        direction = "SELL"
                        entry_price = sell_limit_p
                        position_opened = True
                    elif buy_trigger and sell_trigger:
                        buy_dist = anchor_price - b_low
                        sell_dist = b_high - anchor_price
                        if buy_dist >= sell_dist:
                            direction = "BUY"
                            entry_price = buy_limit_p
                        else:
                            direction = "SELL"
                            entry_price = sell_limit_p
                        position_opened = True

                if position_opened:
                    if direction == "BUY":
                        worst_floating = (b_low - entry_price) * usd_per_point
                        if worst_floating < max_drawdown_usd:
                            max_drawdown_usd = worst_floating

                        # Check TP at Anchor Price P0
                        if b_high >= anchor_price:
                            daily_pnl = (anchor_price - entry_price) * usd_per_point
                            tp_hit = True
                            break

                    elif direction == "SELL":
                        worst_floating = (entry_price - b_high) * usd_per_point
                        if worst_floating < max_drawdown_usd:
                            max_drawdown_usd = worst_floating

                        # Check TP at Anchor Price P0
                        if b_low <= anchor_price:
                            daily_pnl = (entry_price - anchor_price) * usd_per_point
                            tp_hit = True
                            break

            # If position opened but TP not hit by 12:00 PM ICT -> Time Cutoff
            if position_opened and not tp_hit:
                cutoff_hit = True
                last_bar = window_10_12.iloc[-1]
                exit_price = float(last_bar['close'])

                if direction == "BUY":
                    daily_pnl = (exit_price - entry_price) * usd_per_point
                    worst_floating = (float(last_bar['low']) - entry_price) * usd_per_point
                else:
                    daily_pnl = (entry_price - exit_price) * usd_per_point
                    worst_floating = (entry_price - float(last_bar['high'])) * usd_per_point

                if worst_floating < max_drawdown_usd:
                    max_drawdown_usd = worst_floating

            cumulative_balance += daily_pnl
            if cumulative_balance > peak_cumulative_equity:
                peak_cumulative_equity = cumulative_balance

            daily_pnl_pct = (daily_pnl / start_day_equity) * 100.0 if start_day_equity > 0 else 0.0
            drawdown_usd_abs = abs(min(max_drawdown_usd, 0.0))
            if daily_pnl < 0:
                drawdown_usd_abs = max(drawdown_usd_abs, abs(daily_pnl))

            drawdown_pct = (drawdown_usd_abs / start_day_equity) * 100.0 if start_day_equity > 0 else 0.0

            daily_logs.append({
                "date": date_str,
                "anchor_price_10am": round(anchor_price, 3),
                "atr14_m5": round(raw_atr, 3),
                "k_multiplier": k_multiplier,
                "entry_distance_pts": round(d_entry, 3),
                "active_lot_size": active_lot,
                "direction": direction if position_opened else "NO_ENTRY",
                "position_opened": position_opened,
                "tp_hit": tp_hit,
                "cutoff_hit": cutoff_hit,
                "daily_pnl_usd": round(daily_pnl, 2),
                "daily_pnl_pct": round(daily_pnl_pct, 2),
                "ending_equity_usd": round(cumulative_balance, 2),
                "max_drawdown_usd": round(drawdown_usd_abs, 2),
                "max_drawdown_pct": round(drawdown_pct, 2)
            })

        return daily_logs, cumulative_balance
