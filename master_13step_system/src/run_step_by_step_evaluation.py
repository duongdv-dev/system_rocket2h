import os
import json
import pandas as pd
from master_13step_backtester import Master13StepBacktester

STEP_NAMES = {
    0: "Step 0: Baseline (DCA thô không AI)",
    1: "Step 1: Trade / Skip (Gatekeeper Risk Filter)",
    2: "Step 2: Volume Selection (Multi-bucket Vol Sizing)",
    3: "Step 3: Entry Distance Profile (Near/Standard/Far)",
    4: "Step 4: DCA Step Profile (Standard/Wide DCA)",
    5: "Step 5: Allow / Stop DCA Breaker (In-session Breaker)",
    6: "Step 6: Continuous Entry Tuning (Miền liên tục)",
    7: "Step 7: Continuous DCA Step Tuning",
    8: "Step 8: Early Exit 11h30 (Thoát sớm rủi ro)",
    9: "Step 9: Multi-Checkpoint 10h30/11h00/11h30",
    10: "Step 10: Asymmetric Buy / Sell Parameters",
    11: "Step 11: Dynamic Breakeven TP tại 11h00",
    12: "Step 12: Dynamic Reduced TP 50% tại 11h30",
    13: "Step 13: Master Model Pruning (Kháng Overfitting)"
}

def run_step_by_step_evaluation():
    print("=" * 105)
    print("🔍 KHỞI CHẠY BÁO CÁO KIỂM CHỨNG TỪNG BƯỚC (STEP-BY-STEP EVALUATION: STEP 0 -> STEP 13)")
    print("=" * 105)

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
        for p in possible_paths:
            if os.path.exists(p):
                test_paths.append(p)
                break

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "ai_master_model.joblib")

    backtester = Master13StepBacktester(test_paths, model_path=model_path, default_lot=0.60)

    step_results = []

    print(f"{'BƯỚC':<8} | {'TÊN BƯỚC PHÁT TRIỂN AI':<45} | {'EQUITY ($)':<12} | {'NET PNL ($)':<12} | {'RETURN (%)':<10} | {'WINRATE (%)':<11} | {'TP/SL/EXIT':<12} | {'SKIP':<6}")
    print("-" * 125)

    for step in range(0, 14):
        summary, _ = backtester.run_13step_backtest(max_step=step)
        step_results.append(summary)

        name = STEP_NAMES.get(step, f"Step {step}")
        eq_str = f"${summary['final_equity']:,.2f}"
        pnl_str = f"${summary['net_pnl_usd']:,.2f}"
        ret_str = f"{summary['return_pct']:+.2f}%"
        wr_str = f"{summary['win_rate_pct']:.1f}%"
        tpsl_str = f"{summary['tp_days']}/{summary['sl_days']}/{summary['early_exit_days']}"
        skip_str = f"{summary['skipped_days']}d"

        print(f"Step {step:<3} | {name:<45} | {eq_str:<12} | {pnl_str:<12} | {ret_str:<10} | {wr_str:<11} | {tpsl_str:<12} | {skip_str:<6}")

    print("=" * 125)

    matrix_path = os.path.join(output_dir, "step_by_step_comparison_matrix.json")
    with open(matrix_path, "w") as f:
        json.dump(step_results, f, indent=4)

    print(f"\n✅ Đã lưu kết quả đối soát từng bước vào: {matrix_path}")

if __name__ == "__main__":
    run_step_by_step_evaluation()
