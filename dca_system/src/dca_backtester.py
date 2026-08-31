import os
import json
import pytz
import pandas as pd
import numpy as np
from datetime import datetime, time

class DCABacktester:
    def __init__(self, data_paths, initial_balance=10000.0, default_lot=0.40, lot_usd_per_point=100.0, max_daily_loss_pct=20.0):
        """
        DCA Strategy Backtester for XAUUSD (2020-2024)
        
        :param data_paths: List of paths to M1 CSV files
        :param initial_balance: Starting account equity in USD
        :param default_lot: Fixed volume size per DCA position (default 0.40 Lot)
        :param lot_usd_per_point: USD profit/loss per 1.0 price unit move per lot size (0.1 lot = $10/point)
        :param max_daily_loss_pct: Max allowed daily loss in % of starting daily equity (default 20.0%)
        """
        self.data_paths = data_paths
        self.initial_balance = initial_balance
        self.default_lot = default_lot
        self.lot_usd_per_point = lot_usd_per_point
        self.max_daily_loss_pct = max_daily_loss_pct
        self.tz_ict = pytz.timezone("Asia/Ho_Chi_Minh")

    def load_and_preprocess_data(self):
        df_list = []
        for path in self.data_paths:
            if not os.path.exists(path):
                print(f"Warning: File not found at {path}")
                continue
            print(f"Loading data from: {path}")
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

    def run_backtest(self):
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
                atr_step = 1.5
            else:
                atr_step = float(m5_prior['atr14'].iloc[-1])

            atr_step = max(atr_step, 0.1)

            direction = "NONE"
            positions = []
            max_level = 0
            tp_hit = False
            sl_hit = False
            session_closed = False
            daily_pnl = 0.0
            max_drawdown_usd = 0.0

            start_day_equity = cumulative_balance
            max_allowed_loss_usd = start_day_equity * (self.max_daily_loss_pct / 100.0)
            usd_per_point = self.default_lot * self.lot_usd_per_point

            for idx, bar in window_10_12.iterrows():
                if session_closed:
                    break

                b_high = float(bar['high'])
                b_low = float(bar['low'])

                if direction == "NONE":
                    buy_trigger = b_low <= (anchor_price - atr_step)
                    sell_trigger = b_high >= (anchor_price + atr_step)

                    if buy_trigger and not sell_trigger:
                        direction = "BUY"
                    elif sell_trigger and not buy_trigger:
                        direction = "SELL"
                    elif buy_trigger and sell_trigger:
                        buy_dist = anchor_price - b_low
                        sell_dist = b_high - anchor_price
                        direction = "BUY" if buy_dist >= sell_dist else "SELL"

                if direction == "BUY":
                    curr_max_k = int(np.floor((anchor_price - b_low) / atr_step))
                    if curr_max_k > max_level:
                        for k in range(max_level + 1, curr_max_k + 1):
                            entry_p = anchor_price - k * atr_step
                            positions.append({'level': k, 'entry_price': entry_p, 'lot': self.default_lot})
                        max_level = curr_max_k

                    if positions:
                        worst_floating = sum((b_low - pos['entry_price']) * usd_per_point for pos in positions)
                        if worst_floating < max_drawdown_usd:
                            max_drawdown_usd = worst_floating

                        if abs(worst_floating) >= max_allowed_loss_usd and worst_floating < 0:
                            daily_pnl = -max_allowed_loss_usd
                            sl_hit = True
                            session_closed = True
                            break

                    if b_high >= anchor_price:
                        daily_pnl = sum((anchor_price - pos['entry_price']) * usd_per_point for pos in positions)
                        tp_hit = True
                        session_closed = True
                        break

                elif direction == "SELL":
                    curr_max_k = int(np.floor((b_high - anchor_price) / atr_step))
                    if curr_max_k > max_level:
                        for k in range(max_level + 1, curr_max_k + 1):
                            entry_p = anchor_price + k * atr_step
                            positions.append({'level': k, 'entry_price': entry_p, 'lot': self.default_lot})
                        max_level = curr_max_k

                    if positions:
                        worst_floating = sum((pos['entry_price'] - b_high) * usd_per_point for pos in positions)
                        if worst_floating < max_drawdown_usd:
                            max_drawdown_usd = worst_floating

                        if abs(worst_floating) >= max_allowed_loss_usd and worst_floating < 0:
                            daily_pnl = -max_allowed_loss_usd
                            sl_hit = True
                            session_closed = True
                            break

                    if b_low <= anchor_price:
                        daily_pnl = sum((pos['entry_price'] - anchor_price) * usd_per_point for pos in positions)
                        tp_hit = True
                        session_closed = True
                        break

            if not session_closed:
                last_bar = window_10_12.iloc[-1]
                exit_price = float(last_bar['close'])

                if direction == "BUY" and positions:
                    daily_pnl = sum((exit_price - pos['entry_price']) * usd_per_point for pos in positions)
                elif direction == "SELL" and positions:
                    daily_pnl = sum((pos['entry_price'] - exit_price) * usd_per_point for pos in positions)
                else:
                    daily_pnl = 0.0
                
                session_closed = True

            if daily_pnl < -max_allowed_loss_usd:
                daily_pnl = -max_allowed_loss_usd
                sl_hit = True

            cumulative_balance += daily_pnl
            if cumulative_balance > peak_cumulative_equity:
                peak_cumulative_equity = cumulative_balance

            drawdown_usd_abs = abs(min(max_drawdown_usd, 0.0))
            if daily_pnl < 0:
                drawdown_usd_abs = max(drawdown_usd_abs, abs(daily_pnl))

            drawdown_pct = (drawdown_usd_abs / start_day_equity) * 100.0 if start_day_equity > 0 else 0.0

            daily_logs.append({
                "date": date_str,
                "anchor_price_10am": round(anchor_price, 3),
                "atr14_m5_step": round(atr_step, 3),
                "direction": direction,
                "trades_count": len(positions),
                "tp_hit": tp_hit,
                "sl_hit": sl_hit,
                "daily_pnl_usd": round(daily_pnl, 2),
                "ending_equity_usd": round(cumulative_balance, 2),
                "max_drawdown_usd": round(drawdown_usd_abs, 2),
                "max_drawdown_pct": round(drawdown_pct, 2)
            })

        return daily_logs, cumulative_balance
