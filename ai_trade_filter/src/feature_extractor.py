import os
import pytz
import pandas as pd
import numpy as np
from datetime import time

class FeatureExtractor:
    def __init__(self, data_paths):
        self.data_paths = data_paths
        self.tz_ict = pytz.timezone("Asia/Ho_Chi_Minh")

    def load_data(self):
        df_list = []
        for path in self.data_paths:
            if os.path.exists(path):
                print(f"Loading dataset: {os.path.basename(path)}")
                df = pd.read_csv(path)
                df_list.append(df)
        
        if not df_list:
            raise FileNotFoundError("No dataset files found!")
            
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

    def extract_daily_features(self):
        """Extract scale-invariant & directional 10:00 AM features for each trading day."""
        df = self.load_data()
        m5_df = self.compute_m5_atr14(df)
        
        trading_days = sorted(df['date_str'].unique())
        feature_records = []
        atr_history = []

        for date_str in trading_days:
            day_m1 = df[df['date_str'] == date_str].copy()
            if day_m1.empty:
                continue

            target_10am = time(10, 0, 0)
            window_10 = day_m1[day_m1['time'] >= target_10am]
            if window_10.empty:
                continue

            bar_10am = window_10.iloc[0]
            anchor_dt = bar_10am['dt_ict']
            anchor_open = float(bar_10am['open'])

            # 1. ATR14 M5 at 10:00 AM
            m5_prior = m5_df[m5_df.index <= anchor_dt]
            if len(m5_prior) == 0 or pd.isna(m5_prior['atr14'].iloc[-1]):
                atr14 = 1.5
            else:
                atr14 = float(m5_prior['atr14'].iloc[-1])
            
            atr14 = max(atr14, 0.1)
            atr_history.append(atr14)

            # 2. Scale-Invariant ATR Ratio
            mean_atr_20d = np.mean(atr_history[-20:]) if len(atr_history) >= 5 else atr14
            atr_ratio_20d = atr14 / mean_atr_20d if mean_atr_20d > 0 else 1.0

            # 3. Morning range & directional trend (06:00 to 10:00 AM ICT)
            t_6am = time(6, 0, 0)
            t_8am = time(8, 0, 0)
            morning_df = day_m1[(day_m1['time'] >= t_6am) & (day_m1['time'] <= target_10am)]
            
            if not morning_df.empty:
                morning_high = float(morning_df['high'].max())
                morning_low = float(morning_df['low'].min())
                morning_open = float(morning_df.iloc[0]['open'])
                
                morning_range_pts = morning_high - morning_low
                morning_trend_pts = abs(anchor_open - morning_open)
                
                recent_morning = day_m1[(day_m1['time'] >= t_8am) & (day_m1['time'] <= target_10am)]
                if len(recent_morning) > 5:
                    m1_returns = recent_morning['close'].pct_change().dropna()
                    morning_vol_std = float(m1_returns.std() * 1000.0) if not m1_returns.empty else 1.0
                else:
                    morning_vol_std = 1.0
            else:
                morning_range_pts = atr14 * 2.0
                morning_trend_pts = atr14
                morning_vol_std = 1.0

            # Directional ratio (1-way trend breakout vs 2-sided mean reversion)
            directional_ratio = morning_trend_pts / morning_range_pts if morning_range_pts > 0 else 0.5

            # Scale-invariant ratios (normalized by ATR)
            range_to_atr_ratio = morning_range_pts / atr14 if atr14 > 0 else 1.0
            trend_to_atr_ratio = morning_trend_pts / atr14 if atr14 > 0 else 1.0
            day_of_week = int(anchor_dt.weekday())

            feature_records.append({
                "date": date_str,
                "anchor_price_10am": round(anchor_open, 3),
                "atr14_m5": round(atr14, 3),
                "atr_ratio_20d": round(atr_ratio_20d, 3),
                "morning_range_pts": round(morning_range_pts, 3),
                "morning_trend_pts": round(morning_trend_pts, 3),
                "directional_ratio": round(directional_ratio, 3),
                "range_to_atr_ratio": round(range_to_atr_ratio, 3),
                "trend_to_atr_ratio": round(trend_to_atr_ratio, 3),
                "morning_vol_std": round(morning_vol_std, 3),
                "day_of_week": day_of_week
            })

        return pd.DataFrame(feature_records), df
