import os
import sys
import json
import joblib
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from feature_extractor import FeatureExtractor
from volume_backtester import VolumeBacktester
from train_filter import run_step_1_training

def run_volume_optimization_comparison():
    """
    SO SÁNH 3 CHIẾN LƯỢC TRÊN TẬP DỮ LIỆU TEST 2023 - 2024:
    1. Baseline Gốc: Cố định 0.10 Lot, Không lọc.
    2. AI Risk Filter: Cố định 0.10 Lot, Lọc bỏ ngày nguy hiểm.
    3. AI Risk Filter + Dynamic Volume Scaling: Điều chỉnh Lot linh hoạt (0.01 Lot multiples).
    """
    src_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(src_dir)
    workspace_dir = os.path.dirname(base_dir)

    model_path = os.path.join(base_dir, "output", "ai_risk_model.joblib")
    meta_path = os.path.join(base_dir, "output", "ai_model_meta.json")

    if os.path.exists(model_path):
        print(f"✅ ĐÃ TÌM THẤY MÔ HÌNH AI VOLUME OPTIMIZER: {model_path}")
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
    print("   📊 BACKTEST SO SÁNH TỐI ƯU KHỐI LƯỢNG VỊ THẾ DYNAMIC VOLUME (2023 - 2024)")
    print("=" * 80)

    extractor = FeatureExtractor(test_files)
    features_df, _ = extractor.extract_daily_features()

    bt_engine = VolumeBacktester(test_files, ai_model_path=model_path, max_daily_loss_pct=5.0)

    # 1. Baseline Unfiltered Strategy (Fixed 0.10 Lot)
    unfilt_logs, unfilt_final_bal = bt_engine.run_backtest(daily_volume_dict=None)
    df_unfilt = pd.DataFrame(unfilt_logs)

    # 2. Dynamic Volume Optimization
    volume_map, decision_reasons = bt_engine.calculate_daily_dynamic_volumes(features_df)
    dyn_logs, dyn_final_bal = bt_engine.run_backtest(daily_volume_dict=volume_map)
    df_dyn = pd.DataFrame(dyn_logs)

    # Merge logs with decision reasons
    for log in dyn_logs:
        d = log['date']
        log['reason'] = decision_reasons.get(d, "")
        log['status'] = "SKIPPED" if log['active_lot_size'] == 0.00 else ("REDUCED_VOL" if log['active_lot_size'] < 0.10 else "STANDARD_VOL")

    # Metrics
    df_dyn_traded = df_dyn[df_dyn['active_lot_size'] > 0.0]
    df_unfilt_traded = df_unfilt[df_unfilt['direction'] != 'NONE']

    unfilt_pnl = unfilt_final_bal - 10000.0
    dyn_pnl = dyn_final_bal - 10000.0

    unfilt_tp = len(df_unfilt_traded[df_unfilt_traded['tp_hit'] == True])
    dyn_tp = len(df_dyn_traded[df_dyn_traded['tp_hit'] == True])

    unfilt_sl = len(df_unfilt_traded[df_unfilt_traded['sl_hit'] == True])
    dyn_sl = len(df_dyn_traded[df_dyn_traded['sl_hit'] == True])

    unfilt_winrate = (unfilt_tp / len(df_unfilt_traded) * 100) if len(df_unfilt_traded) > 0 else 0
    dyn_winrate = (dyn_tp / len(df_dyn_traded) * 100) if len(df_dyn_traded) > 0 else 0

    unfilt_max_dd = df_unfilt['max_drawdown_usd'].max()
    dyn_max_dd = df_dyn['max_drawdown_usd'].max()

    comparison_report = {
        "training_phase_ai_meta": meta_info,
        "test_phase_2023_2024": {
            "baseline_unfiltered": {
                "initial_capital": 10000.0,
                "final_equity": round(unfilt_final_bal, 2),
                "net_pnl_usd": round(unfilt_pnl, 2),
                "return_pct": round((unfilt_pnl / 10000.0) * 100, 2),
                "volume_mode": "Fixed 0.10 Lot",
                "total_trading_days": len(df_unfilt_traded),
                "tp_hit_days": unfilt_tp,
                "sl_hit_days": unfilt_sl,
                "win_rate_pct": round(unfilt_winrate, 2),
                "max_drawdown_usd": round(unfilt_max_dd, 2),
                "max_drawdown_pct": round((unfilt_max_dd / 10000.0) * 100, 2)
            },
            "ai_dynamic_volume_strategy": {
                "initial_capital": 10000.0,
                "final_equity": round(dyn_final_bal, 2),
                "net_pnl_usd": round(dyn_pnl, 2),
                "return_pct": round((dyn_pnl / 10000.0) * 100, 2),
                "volume_mode": "Dynamic Volume (0.01 Lot Multiples)",
                "total_trading_days": len(df_dyn_traded),
                "skipped_days_count": len(df_dyn[df_dyn['active_lot_size'] == 0.00]),
                "reduced_vol_days_count": len(df_dyn[(df_dyn['active_lot_size'] > 0.00) & (df_dyn['active_lot_size'] < 0.10)]),
                "standard_vol_days_count": len(df_dyn[df_dyn['active_lot_size'] == 0.10]),
                "tp_hit_days": dyn_tp,
                "sl_hit_days": dyn_sl,
                "win_rate_pct": round(dyn_winrate, 2),
                "max_drawdown_usd": round(dyn_max_dd, 2),
                "max_drawdown_pct": round((dyn_max_dd / 10000.0) * 100, 2)
            }
        },
        "daily_results": dyn_logs
    }

    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "comparison_report.json")
    results_path = os.path.join(output_dir, "filtered_results_2023_2024.json")

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_report, f, indent=4, ensure_ascii=False)

    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({"summary": comparison_report["test_phase_2023_2024"]["ai_dynamic_volume_strategy"], "daily_results": dyn_logs}, f, indent=4, ensure_ascii=False)

    print("\n================ OUT-OF-SAMPLE DYNAMIC VOLUME RESULTS (2023 - 2024) ================")
    print(f"METRIC                   | BASELINE (FIXED 0.10 LOT) | AI DYNAMIC VOLUME SCALING")
    print(f"-------------------------+---------------------------+------------------------------")
    print(f"Net Profit (USD)         | ${unfilt_pnl:,.2f}                 | ${dyn_pnl:,.2f}")
    print(f"Total Return (%)         | {comparison_report['test_phase_2023_2024']['baseline_unfiltered']['return_pct']}%                    | {comparison_report['test_phase_2023_2024']['ai_dynamic_volume_strategy']['return_pct']}%")
    print(f"Win Rate (%)             | {unfilt_winrate:.2f}%                   | {dyn_winrate:.2f}%")
    print(f"Trading Days             | {len(df_unfilt_traded)} days                | {len(df_dyn_traded)} days")
    print(f"Skipped Days (0.00 Lot)  | 0 days                    | {len(df_dyn[df_dyn['active_lot_size'] == 0.00])} days")
    print(f"Reduced Vol Days (<0.10) | 0 days                    | {len(df_dyn[(df_dyn['active_lot_size'] > 0.00) & (df_dyn['active_lot_size'] < 0.10)])} days")
    print(f"Standard Vol (0.10 Lot)  | 514 days                  | {len(df_dyn[df_dyn['active_lot_size'] == 0.10])} days")
    print(f"Max Drawdown (USD)       | ${unfilt_max_dd:,.2f}                 | ${dyn_max_dd:,.2f}")
    print(f"Max Drawdown (%)         | {comparison_report['test_phase_2023_2024']['baseline_unfiltered']['max_drawdown_pct']}%                    | {comparison_report['test_phase_2023_2024']['ai_dynamic_volume_strategy']['max_drawdown_pct']}%")
    print(f"====================================================================================\n")

if __name__ == "__main__":
    run_volume_optimization_comparison()
