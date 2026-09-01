import numpy as np

class StepOptimizer:
    """
    Master System Optimizer (Ultra-Growth Engine: Target +500% to +1000% Net Return):
    - Base Lot: 0.60 Lot (Scaled with Auto Compounding)
    - Min Defense Lot: 0.35 Lot
    - Tight Attack Step: 0.50x ATR
    - Tightened Defense Step: 0.65x ATR
    - Skip Threshold: 0.45 (nới ngưỡng để ăn 300+ ngày chốt lời TP)
    """
    def __init__(self, base_lot=0.60, min_lot=0.35, safe_step_mult=0.50, moderate_step_mult=0.65):
        self.base_lot = base_lot
        self.min_lot = min_lot
        self.safe_step_mult = safe_step_mult
        self.moderate_step_mult = moderate_step_mult

    def compute_master_config(self, prob_risk, skip_threshold=0.45, safe_threshold=0.20):
        if prob_risk >= skip_threshold:
            return {
                "lot": 0.00,
                "step_mult": 1.00,
                "reason": f"🛑 AI BỎ QUA (SKIP): P={prob_risk*100:.1f}% ≥ {skip_threshold*100:.1f}%"
            }

        if prob_risk < safe_threshold:
            return {
                "lot": round(self.base_lot, 2),
                "step_mult": self.safe_step_mult,
                "reason": f"🔥 TẤN CÔNG BỨT PHÁ (Base {self.base_lot}L | Step {self.safe_step_mult}x ATR): P={prob_risk*100:.1f}% An Toàn Cao"
            }

        ratio = (skip_threshold - prob_risk) / (skip_threshold - safe_threshold)
        raw_lot = self.min_lot + ratio * (self.base_lot - self.min_lot)
        active_lot = round(raw_lot, 2)
        active_lot = max(self.min_lot, min(self.base_lot, active_lot))

        return {
            "lot": active_lot,
            "step_mult": self.moderate_step_mult,
            "reason": f"🛡️ PHÒNG THỦ TỐI ƯU (Vol {active_lot}L | Step Gọn {self.moderate_step_mult}x ATR): P={prob_risk*100:.1f}%"
        }
