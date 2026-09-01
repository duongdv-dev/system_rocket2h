import os
import sys
import json
import joblib
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from feature_extractor import FeatureExtractor
from step_backtester import StepBacktester
from train_filter import run_step_1_training

def run_master_system_comparison():
    """
    HIGH-YIELD MASTER SYSTEM MODE: TARGET +300% TO +500% RETURN (2023 - 2024)
    - Base Lot: 1.20 Lot
    - Daily Max Loss Cap: 30.0% (-$3,000 USD)
    - Trading Window: 10:00 - 12:00 ICT
    """
    src_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(src_dir)
    workspace_dir = os.path.dirname(base_dir)

    model_path = os.path.join(base_dir, "output", "ai_risk_model.joblib")
    meta_path = os.path.join(base_dir, "output", "ai_model_meta.json")

    if os.path.exists(model_path):
        print(f"✅ ĐÃ TÌM THẤY MÔ HÌNH AI MASTER SYSTEM: {model_path}")
        meta_info = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_info = json.load(f)
    else:
        print("⚠️ CHƯA TÌM THẤY MÔ HÌNH AI. Tiến hành chạy Training (2020 - 2023)...")
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
    print("   📊 BACKTEST HIGH-YIELD MASTER SYSTEM (BASE 1.20 LOT | DAILY LOSS CAP 30%)")
    print("=" * 80)

    extractor = FeatureExtractor(test_files)
    features_df, _ = extractor.extract_daily_features()

    bt_engine = StepBacktester(test_files, ai_model_path=model_path, default_lot=1.20, max_daily_loss_pct=30.0)

    unfilt_logs, unfilt_final_bal = bt_engine.run_backtest(daily_config_dict=None, step_multiplier=1.0)
    df_unfilt = pd.DataFrame(unfilt_logs)

    master_config_map = bt_engine.calculate_master_daily_configs(features_df)
    master_logs, master_final_bal = bt_engine.run_backtest(daily_config_dict=master_config_map)
    df_master = pd.DataFrame(master_logs)

    for log in master_logs:
        d = log['date']
        cfg = master_config_map.get(d, {})
        log['reason'] = cfg.get('reason', "")
        log['status'] = "SKIPPED" if log['active_lot_size'] == 0.00 else ("ATTACK" if log['step_multiplier'] < 0.70 else "DEFENSE")

    df_master_traded = df_master[df_master['active_lot_size'] > 0.0]
    df_unfilt_traded = df_unfilt[df_unfilt['direction'] != 'NONE']

    unfilt_pnl = unfilt_final_bal - 10000.0
    master_pnl = master_final_bal - 10000.0

    unfilt_tp = len(df_unfilt_traded[df_unfilt_traded['tp_hit'] == True])
    master_tp = len(df_master_traded[df_master_traded['tp_hit'] == True])

    unfilt_sl = len(df_unfilt_traded[df_unfilt_traded['sl_hit'] == True])
    master_sl = len(df_master_traded[df_master_traded['sl_hit'] == True])

    unfilt_winrate = (unfilt_tp / len(df_unfilt_traded) * 100) if len(df_unfilt_traded) > 0 else 0
    master_winrate = (master_tp / len(df_master_traded) * 100) if len(df_master_traded) > 0 else 0

    unfilt_max_dd = df_unfilt['max_drawdown_usd'].max()
    master_max_dd = df_master['max_drawdown_usd'].max()

    comparison_report = {
        "training_phase_ai_meta": meta_info,
        "test_phase_2023_2024": {
            "baseline_unfiltered": {
                "initial_capital": 10000.0,
                "final_equity": round(unfilt_final_bal, 2),
                "net_pnl_usd": round(unfilt_pnl, 2),
                "return_pct": round((unfilt_pnl / 10000.0) * 100, 2),
                "base_lot": 1.20,
                "max_daily_loss_pct_cap": 30.0,
                "total_trading_days": len(df_unfilt_traded),
                "tp_hit_days": unfilt_tp,
                "sl_hit_days": unfilt_sl,
                "win_rate_pct": round(unfilt_winrate, 2),
                "max_drawdown_usd": round(unfilt_max_dd, 2),
                "max_drawdown_pct": round((unfilt_max_dd / 10000.0) * 100, 2)
            },
            "master_system_combined": {
                "initial_capital": 10000.0,
                "final_equity": round(master_final_bal, 2),
                "net_pnl_usd": round(master_pnl, 2),
                "return_pct": round((master_pnl / 10000.0) * 100, 2),
                "mode": "High-Yield Master System (Base 1.20 Lot | Daily Cap 30.0% | Target +300% to +500%)",
                "base_lot": 1.20,
                "max_daily_loss_pct_cap": 30.0,
                "trading_window": "10:00 - 12:00 ICT",
                "total_trading_days": len(df_master_traded),
                "skipped_days_count": len(df_master[df_master['active_lot_size'] == 0.00]),
                "attack_days_count": len(df_master[df_master['step_multiplier'] < 0.70]),
                "defense_days_count": len(df_master[(df_master['active_lot_size'] > 0.00) & (df_master['step_multiplier'] >= 0.70)]),
                "tp_hit_days": master_tp,
                "sl_hit_days": master_sl,
                "win_rate_pct": round(master_winrate, 2),
                "max_drawdown_usd": round(master_max_dd, 2),
                "max_drawdown_pct": round((master_max_dd / 10000.0) * 100, 2)
            }
        },
        "daily_results": master_logs
    }

    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "comparison_report.json")
    results_path = os.path.join(output_dir, "filtered_results_2023_2024.json")

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_report, f, indent=4, ensure_ascii=False)

    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({"summary": comparison_report["test_phase_2023_2024"]["master_system_combined"], "daily_results": master_logs}, f, indent=4, ensure_ascii=False)

    print("\n================ OUT-OF-SAMPLE MASTER SYSTEM RESULTS (HIGH-YIELD 1.20L | CAP 30%) ================")
    print(f"METRIC                   | BASELINE (1.20L UNFILTERED) | MASTER SYSTEM HIGH-YIELD (BASE 1.20L)")
    print(f"-------------------------+------------------------------+--------------------------------------")
    print(f"Net Profit (USD)         | ${unfilt_pnl:,.2f}                | ${master_pnl:,.2f}")
    print(f"Total Return (%)         | {comparison_report['test_phase_2023_2024']['baseline_unfiltered']['return_pct']}%               | {comparison_report['test_phase_2023_2024']['master_system_combined']['return_pct']}%")
    print(f"Win Rate (%)             | {unfilt_winrate:.2f}%                  | {master_winrate:.2f}%")
    print(f"Trading Days             | {len(df_unfilt_traded)} days               | {len(df_master_traded)} days")
    print(f"Skipped Days (0.00 Lot)  | 0 days                   | {len(df_master[df_master['active_lot_size'] == 0.00])} days")
    print(f"Attack Days (0.50 Step)  | 0 days                   | {len(df_master[df_master['step_multiplier'] < 0.70])} days")
    print(f"Defense Days (0.85 Step) | 0 days                   | {len(df_master[(df_master['active_lot_size'] > 0.00) & (df_master['step_multiplier'] >= 0.70)])} days")
    print(f"Max Drawdown (USD)       | ${unfilt_max_dd:,.2f}                | ${master_max_dd:,.2f}")
    print(f"SL 30% Hit Days          | {unfilt_sl} days                  | {master_sl} days")
    print(f"====================================================================================================\n")

if __name__ == "__main__":
    run_master_system_comparison()
