import numpy as np

class VolumeOptimizer:
    """
    Module Tối Ưu Hóa Khối Lượng Vị Thế Động (Base 0.60 Lot).
    Quy đổi khối lượng thực tế về BỘI SỐ CHUẨN CỦA 0.01 LOT.
    """
    def __init__(self, base_lot=0.60, min_lot=0.12, max_lot=0.60):
        self.base_lot = base_lot
        self.min_lot = min_lot
        self.max_lot = max_lot

    def compute_bucket_lot(self, prob_risk, skip_threshold=0.36, safe_threshold=0.20):
        if prob_risk >= skip_threshold:
            return 0.00

        if prob_risk < safe_threshold:
            return round(self.base_lot, 2)

        ratio = (skip_threshold - prob_risk) / (skip_threshold - safe_threshold)
        raw_lot = self.min_lot + ratio * (self.base_lot - self.min_lot)
        lot = round(raw_lot, 2)
        lot = max(self.min_lot, min(self.max_lot, lot))
        return round(lot, 2)

    def compute_volatility_lot(self, atr_ratio_20d):
        if atr_ratio_20d <= 1.0:
            return round(self.base_lot, 2)

        raw_lot = self.base_lot / atr_ratio_20d
        lot = round(raw_lot, 2)
        lot = max(self.min_lot, min(self.max_lot, lot))
        return round(lot, 2)
