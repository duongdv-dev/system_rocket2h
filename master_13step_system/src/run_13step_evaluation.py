import os
import json
import pandas as pd
from master_13step_backtester import Master13StepBacktester

def run_evaluation():
    print("=" * 70)
    print("⚡ KHỞI CHẠY BÁO CÁO ĐÁNH GIÁ 13 BƯỚC AI MASTER SYSTEM (2023 - 2025)")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = ["XAUUSD_2023_m1.csv", "XAUUSD_2024_m1.csv", "XAUUSD_2025_m1.csv"]
    
    test_paths = []
    for f in files:
        possible_paths = [
            os.path.join(base_dir, f),
            os.path.join("/app/data", f),
            os.path.join("/app", f),
            os.path.join(".", f)
        ]
        found = False
        for p in possible_paths:
            if os.path.exists(p):
                test_paths.append(p)
                found = True
                break
        if not found:
            print(f"Warning: {f} not found in candidate locations.")

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "ai_master_model.joblib")

    # 1. Chạy Baseline Thô (Chưa qua AI)
    print("\n--- 1. Mô Phỏng Strategy Baseline DCA Thô ---")
    backtester_base = Master13StepBacktester(test_paths, model_path=None, default_lot=0.60)
    summary_base, logs_base = backtester_base.run_13step_backtest()

    # 2. Chạy Master 13-Step AI System
    print("\n--- 2. Mô Phỏng Master System 13 Lớp AI ---")
    backtester_ai = Master13StepBacktester(test_paths, model_path=model_path, default_lot=0.60)
    summary_ai, logs_ai = backtester_ai.run_13step_backtest()

    report = {
        "evaluation_period": "2023 - 2025",
        "baseline_unfiltered": summary_base,
        "master_13step_ai": summary_ai
    }

    report_path = os.path.join(output_dir, "comparison_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)

    results_path = os.path.join(output_dir, "filtered_results_2023_2025.json")
    with open(results_path, "w") as f:
        json.dump({"summary": summary_ai, "daily_results": logs_ai}, f, indent=4)

    print("\n" + "=" * 70)
    print("🏆 KẾT QUẢ ĐỐI SOÁT HIỆU NĂNG 13 BƯỚC AI")
    print("=" * 70)
    print(f"🔹 Baseline Equity: ${summary_base['final_equity']} | PnL: ${summary_base['net_pnl_usd']} ({summary_base['return_pct']}%)")
    print(f"🔥 Master AI Equity: ${summary_ai['final_equity']} | PnL: ${summary_ai['net_pnl_usd']} ({summary_ai['return_pct']}%)")
    print(f"🎯 Win Rate Master AI: {summary_ai['win_rate_pct']}% (TP: {summary_ai['tp_days']} | SL: {summary_ai['sl_days']} | Early Exit: {summary_ai['early_exit_days']})")
    print(f"🛑 Skipped High-Risk Days: {summary_ai['skipped_days']} / {summary_ai['total_trading_days']} ngày")
    print("=" * 70)

if __name__ == "__main__":
    run_evaluation()
