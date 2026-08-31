import os
import sys
import json
import joblib
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from feature_extractor import FeatureExtractor
from filter_backtester import FilterBacktester
from train_filter import run_step_1_training

def run_out_of_sample_comparison():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(src_dir)
    workspace_dir = os.path.dirname(base_dir)

    model_path = os.path.join(base_dir, "output", "ai_risk_model.joblib")
    meta_path = os.path.join(base_dir, "output", "ai_model_meta.json")

    if os.path.exists(model_path):
        print(f"✅ ĐÃ TÌM THẤY MÔ HÌNH AI ĐÃ TRAIN: {model_path}")
        meta_info = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_info = json.load(f)
    else:
        print("⚠️ CHƯA TÌM THẤY MÔ HÌNH AI. Bắt đầu chạy Training (2020 - 2023)...")
        model, meta_info = run_step_1_training()

    possible_path_sets = [
        [
            os.path.join(workspace_dir, "XAUUSD_2023_m1.csv"),
            os.path.join(workspace_dir, "XAUUSD_2024_m1.csv")
        ],
        [
            os.path.join(base_dir, "..", "XAUUSD_2023_m1.csv"),
            os.path.join(base_dir, "..", "XAUUSD_2024_m1.csv")
        ],
        [
            "/app/data/XAUUSD_2023_m1.csv",
            "/app/data/XAUUSD_2024_m1.csv"
        ]
    ]

    test_files = None
    for path_set in possible_path_sets:
        if all(os.path.exists(p) for p in path_set):
            test_files = path_set
            break

    if not test_files:
        raise FileNotFoundError("Không tìm thấy các file dữ liệu CSV 2023-2024!")

    print("\n" + "=" * 80)
    print("   📊 BACKTEST OUT-OF-SAMPLE (2023 - 2024) [BASE 0.40 LOT | DAILY LOSS CAP 20%]")
    print("=" * 80)

    extractor = FeatureExtractor(test_files)
    features_df, _ = extractor.extract_daily_features()

    bt_unfiltered = FilterBacktester(test_files, ai_model_path=None, default_lot=0.40, max_daily_loss_pct=20.0)
    unfiltered_logs, unfilt_final_bal = bt_unfiltered.run_backtest()
    df_unfilt = pd.DataFrame(unfiltered_logs)

    cols_to_drop = [c for c in ['anchor_price_10am', 'atr14_m5_step', 'atr14_m5'] if c in df_unfilt.columns]
    df_unfilt_clean = df_unfilt.drop(columns=cols_to_drop, errors='ignore')

    bt_filtered = FilterBacktester(test_files, ai_model_path=model_path, default_lot=0.40, max_daily_loss_pct=20.0)
    merged = pd.merge(features_df, df_unfilt_clean, on='date')

    filtered_daily_logs = []
    filtered_balance = 10000.0
    peak_balance = 10000.0
    max_dd_usd = 0.0

    skipped_days = []
    saved_loss_total = 0.0

    for idx, row in merged.iterrows():
        date_str = row['date']
        should_trade, reason = bt_filtered.evaluate_filter_decision(row)
        atr_val = row.get('atr14_m5', row.get('atr14_m5_step', 1.5))

        if should_trade:
            day_pnl = float(row['daily_pnl_usd'])
            filtered_balance += day_pnl
            if filtered_balance > peak_balance:
                peak_balance = filtered_balance
            
            dd = peak_balance - filtered_balance
            if dd > max_dd_usd:
                max_dd_usd = dd

            filtered_daily_logs.append({
                "date": date_str,
                "anchor_price_10am": row['anchor_price_10am'],
                "atr14_m5_step": atr_val,
                "direction": row['direction'],
                "trades_count": row['trades_count'],
                "tp_hit": row['tp_hit'],
                "sl_hit": row['sl_hit'],
                "status": "TRADED",
                "filter_reason": reason,
                "daily_pnl_usd": day_pnl,
                "ending_equity_usd": round(filtered_balance, 2),
                "max_drawdown_usd": row['max_drawdown_usd'],
                "max_drawdown_pct": row['max_drawdown_pct']
            })
        else:
            unfilt_pnl = float(row['daily_pnl_usd'])
            if unfilt_pnl < 0:
                saved_loss_total += abs(unfilt_pnl)

            skipped_days.append({
                "date": date_str,
                "reason": reason,
                "unfiltered_pnl_usd": unfilt_pnl
            })

            filtered_daily_logs.append({
                "date": date_str,
                "anchor_price_10am": row['anchor_price_10am'],
                "atr14_m5_step": atr_val,
                "direction": row['direction'],
                "trades_count": 0,
                "tp_hit": False,
                "sl_hit": False,
                "status": "SKIPPED",
                "filter_reason": reason,
                "daily_pnl_usd": 0.0,
                "ending_equity_usd": round(filtered_balance, 2),
                "max_drawdown_usd": 0.0,
                "max_drawdown_pct": 0.0
            })

    df_filt_res = pd.DataFrame([l for l in filtered_daily_logs if l['status'] == 'TRADED' and l['direction'] != 'NONE'])
    unfilt_traded = df_unfilt[df_unfilt['direction'] != 'NONE']

    unfilt_pnl = unfilt_final_bal - 10000.0
    filt_pnl = filtered_balance - 10000.0

    unfilt_tp_days = len(unfilt_traded[unfilt_traded['tp_hit'] == True])
    filt_tp_days = len(df_filt_res[df_filt_res['tp_hit'] == True])

    unfilt_sl_days = len(unfilt_traded[unfilt_traded['sl_hit'] == True])
    filt_sl_days = len(df_filt_res[df_filt_res['sl_hit'] == True])

    unfilt_winrate = (unfilt_tp_days / len(unfilt_traded) * 100) if len(unfilt_traded) > 0 else 0
    filt_winrate = (filt_tp_days / len(df_filt_res) * 100) if len(df_filt_res) > 0 else 0

    unfilt_max_dd = df_unfilt['max_drawdown_usd'].max()
    filt_max_dd = max_dd_usd

    comparison_report = {
        "training_phase_ai_meta": meta_info,
        "test_phase_2023_2024": {
            "baseline_unfiltered": {
                "initial_capital": 10000.0,
                "final_equity": round(unfilt_final_bal, 2),
                "net_pnl_usd": round(unfilt_pnl, 2),
                "return_pct": round((unfilt_pnl / 10000.0) * 100, 2),
                "base_lot": 0.40,
                "max_daily_loss_pct_cap": 20.0,
                "total_trading_days": len(unfilt_traded),
                "tp_hit_days": unfilt_tp_days,
                "sl_hit_days": unfilt_sl_days,
                "win_rate_pct": round(unfilt_winrate, 2),
                "max_drawdown_usd": round(unfilt_max_dd, 2),
                "max_drawdown_pct": round((unfilt_max_dd / 10000.0) * 100, 2)
            },
            "ai_filtered_strategy": {
                "initial_capital": 10000.0,
                "final_equity": round(filtered_balance, 2),
                "net_pnl_usd": round(filt_pnl, 2),
                "return_pct": round((filt_pnl / 10000.0) * 100, 2),
                "base_lot": 0.40,
                "max_daily_loss_pct_cap": 20.0,
                "total_trading_days": len(df_filt_res),
                "skipped_days_count": len(skipped_days),
                "saved_loss_usd": round(saved_loss_total, 2),
                "tp_hit_days": filt_tp_days,
                "sl_hit_days": filt_sl_days,
                "win_rate_pct": round(filt_winrate, 2),
                "max_drawdown_usd": round(filt_max_dd, 2),
                "max_drawdown_pct": round((filt_max_dd / 10000.0) * 100, 2)
            }
        },
        "skipped_days_detail": skipped_days
    }

    report_path = os.path.join(base_dir, "output", "comparison_report.json")
    results_path = os.path.join(base_dir, "output", "filtered_results_2023_2024.json")

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_report, f, indent=4, ensure_ascii=False)

    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({"summary": comparison_report["test_phase_2023_2024"]["ai_filtered_strategy"], "daily_results": filtered_daily_logs}, f, indent=4, ensure_ascii=False)

    print(f"Report exported to: {report_path}\n")

if __name__ == "__main__":
    run_out_of_sample_comparison()
