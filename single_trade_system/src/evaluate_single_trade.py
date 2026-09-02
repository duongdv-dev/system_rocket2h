import os
import sys
import json
import joblib
import pandas as pd
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from feature_extractor import FeatureExtractor
from single_trade_backtester import SingleTradeBacktester

def evaluate_2023_2025():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(src_dir)
    workspace_dir = os.path.dirname(base_dir)

    possible_path_sets = [
        [
            os.path.join(workspace_dir, "XAUUSD_2023_m1.csv"),
            os.path.join(workspace_dir, "XAUUSD_2024_m1.csv"),
            os.path.join(workspace_dir, "XAUUSD_2025_m1.csv")
        ],
        [
            os.path.join(base_dir, "..", "XAUUSD_2023_m1.csv"),
            os.path.join(base_dir, "..", "XAUUSD_2024_m1.csv"),
            os.path.join(base_dir, "..", "XAUUSD_2025_m1.csv")
        ],
        [
            "/app/data/XAUUSD_2023_m1.csv",
            "/app/data/XAUUSD_2024_m1.csv",
            "/app/data/XAUUSD_2025_m1.csv"
        ]
    ]

    test_files = None
    for path_set in possible_path_sets:
        if all(os.path.exists(p) for p in path_set):
            test_files = path_set
            break

    if not test_files:
        raise FileNotFoundError("Không tìm thấy các file CSV 2023-2025 để đánh giá!")

    print("\n==================================================================================")
    print("  🚀 EVALUATING SINGLE-TRADE 1% PROFIT SYSTEM (BACKTEST DỮ LIỆU 2023 - 2025)")
    print("==================================================================================")

    output_dir = os.path.join(base_dir, "output")
    model_file = os.path.join(output_dir, "ai_single_risk_model.joblib")

    ai_model = None
    feature_cols = []
    risk_thresh = 0.38

    if os.path.exists(model_file):
        saved_dict = joblib.load(model_file)
        ai_model = saved_dict.get("model")
        feature_cols = saved_dict.get("feature_cols", [])
        risk_thresh = saved_dict.get("risk_threshold", 0.38)
        print(f"Loaded trained AI Risk Filter model from: {model_file}")
    else:
        print("⚠️ chưa tìm thấy ai_single_risk_model.joblib. Sẽ chạy train 2020-2023 trước...")
        from train_single_filter import train_ai_model_2020_2023
        ai_model, meta = train_ai_model_2020_2023()
        feature_cols = meta.get("feature_importances", {}).keys()

    # Extract 2023-2025 daily features for AI prediction
    extractor = FeatureExtractor(test_files)
    features_df, _ = extractor.extract_daily_features()

    if ai_model is not None and len(feature_cols) > 0:
        X_test = features_df[feature_cols]
        if len(ai_model.classes_) > 1:
            class_1_idx = list(ai_model.classes_).index(1) if 1 in ai_model.classes_ else 0
            risk_probs = ai_model.predict_proba(X_test)[:, class_1_idx]
        else:
            risk_probs = np.zeros(len(X_test))

        features_df['p_risk'] = risk_probs
        features_df['ai_skip'] = features_df['p_risk'] >= risk_thresh
        daily_skip_dict = dict(zip(features_df['date'], features_df['ai_skip']))
    else:
        daily_skip_dict = {}

    bt = SingleTradeBacktester(test_files, initial_balance=10000.0, target_tp_pct=1.0)
    
    k_values = [0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5]
    summary_results = []
    detailed_logs_by_k = {}

    for k in k_values:
        # 1. Baseline Single Trade (No AI)
        logs_base, final_bal_base = bt.run_backtest(k_multiplier=k, daily_skip_dict=None)
        df_base = pd.DataFrame(logs_base)
        
        # 2. AI-Filtered Single Trade
        logs_ai, final_bal_ai = bt.run_backtest(k_multiplier=k, daily_skip_dict=daily_skip_dict)
        df_ai = pd.DataFrame(logs_ai)

        def calc_kpis(df, final_bal, mode_name, k_val):
            total_days = len(df)
            active_trades = df[df['position_opened'] == True]
            num_trades = len(active_trades)
            fill_rate = (num_trades / total_days * 100.0) if total_days > 0 else 0.0
            
            tp_days = len(df[df['tp_hit'] == True])
            win_rate = (tp_days / num_trades * 100.0) if num_trades > 0 else 0.0

            net_pnl = final_bal - 10000.0
            ret_pct = (net_pnl / 10000.0) * 100.0

            # Drawdown
            mdd_usd = df['max_drawdown_usd'].max() if not df.empty else 0.0
            mdd_pct = df['max_drawdown_pct'].max() if not df.empty else 0.0

            # Profit Factor
            gains = df[df['daily_pnl_usd'] > 0]['daily_pnl_usd'].sum()
            losses = abs(df[df['daily_pnl_usd'] < 0]['daily_pnl_usd'].sum())
            profit_factor = round(gains / losses, 2) if losses > 0 else (99.0 if gains > 0 else 0.0)

            return {
                "k_multiplier": k_val,
                "mode": mode_name,
                "total_days": total_days,
                "active_trades": num_trades,
                "fill_rate_pct": round(fill_rate, 1),
                "tp_hit_days": tp_days,
                "win_rate_pct": round(win_rate, 1),
                "initial_balance": 10000.0,
                "final_balance": round(final_bal, 2),
                "net_profit_usd": round(net_pnl, 2),
                "return_pct": round(ret_pct, 2),
                "max_drawdown_usd": round(mdd_usd, 2),
                "max_drawdown_pct": round(mdd_pct, 2),
                "profit_factor": profit_factor
            }

        kpi_base = calc_kpis(df_base, final_bal_base, "Single-Trade Baseline", k)
        kpi_ai = calc_kpis(df_ai, final_bal_ai, "Single-Trade + AI Filter", k)

        summary_results.append(kpi_base)
        summary_results.append(kpi_ai)

        detailed_logs_by_k[f"k_{k}_baseline"] = logs_base
        detailed_logs_by_k[f"k_{k}_ai_filter"] = logs_ai

    # Export Results
    df_summary = pd.DataFrame(summary_results)
    csv_path = os.path.join(output_dir, "single_trade_evaluation_2023_2025.csv")
    json_path = os.path.join(output_dir, "single_trade_evaluation_2023_2025.json")

    df_summary.to_csv(csv_path, index=False)
    
    export_payload = {
        "evaluation_period": "2023 - 2025",
        "kpis_summary": summary_results,
        "detailed_logs": detailed_logs_by_k
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(export_payload, f, indent=4, ensure_ascii=False)

    print("\n==================================================================================")
    print("📊 BẢNG TỔNG HỢP HIỆU NĂNG STRATEGY SINGLE-TRADE 1% PROFIT (2023 - 2025)")
    print("==================================================================================")
    print(f"{'k ATR':<6} | {'MODE':<24} | {'RETURN %':<10} | {'NET PNL ($)':<12} | {'WIN RATE %':<10} | {'FILL RATE %':<11} | {'MAX DD %':<10} | {'P.FACTOR':<8}")
    print("-" * 110)
    for row in summary_results:
        print(f"{row['k_multiplier']:<6} | {row['mode']:<24} | {row['return_pct']:>9.2f}% | ${row['net_profit_usd']:>11.2f} | {row['win_rate_pct']:>9.1f}% | {row['fill_rate_pct']:>10.1f}% | {row['max_drawdown_pct']:>9.2f}% | {row['profit_factor']:>8.2f}")
    print("==================================================================================\n")

    return df_summary, export_payload

if __name__ == "__main__":
    evaluate_2023_2025()
