import numpy as np

class StepOptimizer:
    """
    Master System Optimizer: Phối hợp 3 Lớp (AI Filter + Dynamic Volume Config B: Base 0.40 Lot + Dynamic Step Size).
    """
    def __init__(self, base_lot=0.40, min_lot=0.08, safe_step_mult=0.50, moderate_step_mult=0.85):
        self.base_lot = base_lot
        self.min_lot = min_lot
        self.safe_step_mult = safe_step_mult
        self.moderate_step_mult = moderate_step_mult

    def compute_master_config(self, prob_risk, skip_threshold=0.36, safe_threshold=0.20):
        """
        Tính đồng thời (lot_size, step_mult) cho từng ngày dựa vào P(Risk):
        - P >= skip_threshold: 0.00 Lot (SKIP), Step 1.0
        - safe_threshold <= P < skip_threshold: Vol 0.15 - 0.30 Lot (bội 0.01 Lot), Step 0.85 (Phòng Thủ)
        - P < safe_threshold: Vol 0.40 Lot (Base Lot B), Step 0.50 (Tấn Công Bứt Phá)
        """
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

        # Moderate risk range
        ratio = (skip_threshold - prob_risk) / (skip_threshold - safe_threshold)
        raw_lot = self.min_lot + ratio * (self.base_lot - self.min_lot)
        active_lot = round(raw_lot, 2)
        active_lot = max(self.min_lot, min(self.base_lot, active_lot))

        return {
            "lot": active_lot,
            "step_mult": self.moderate_step_mult,
            "reason": f"🛡️ PHÒNG THỦ (Giảm Vol {active_lot}L | Step {self.moderate_step_mult}x ATR): P={prob_risk*100:.1f}%"
        }
