import numpy as np

class VolumeOptimizer:
    """
    Module Tối Ưu Hóa Khối Lượng Vị Thế Động (Dynamic Position Sizing).
    Quy đổi khối lượng thực tế về BỘI SỐ CHUẨN CỦA 0.01 LOT (0.02, 0.04, 0.05, 0.07, 0.10 Lot).
    """
    def __init__(self, base_lot=0.10, min_lot=0.02, max_lot=0.10):
        self.base_lot = base_lot
        self.min_lot = min_lot
        self.max_lot = max_lot

    def compute_bucket_lot(self, prob_risk, skip_threshold=0.36, safe_threshold=0.20):
        """
        Tính khối lượng theo dải rủi ro P(Risk):
        - P >= skip_threshold: 0.00 Lot (SKIP)
        - safe_threshold <= P < skip_threshold: Giảm Vol mượt từ 0.03 đến 0.08 Lot (bội 0.01 Lot)
        - P < safe_threshold: 0.10 Lot (Giữ nguyên Vol)
        """
        if prob_risk >= skip_threshold:
            return 0.00

        if prob_risk < safe_threshold:
            return round(self.base_lot, 2)

        # Scale linearly between min_lot and base_lot
        ratio = (skip_threshold - prob_risk) / (skip_threshold - safe_threshold)
        raw_lot = self.min_lot + ratio * (self.base_lot - self.min_lot)
        
        # Round to 2 decimal places (0.01 Lot step)
        lot = round(raw_lot, 2)
        lot = max(self.min_lot, min(self.max_lot, lot))
        return round(lot, 2)

    def compute_volatility_lot(self, atr_ratio_20d):
        """
        Tính khối lượng tỷ lệ nghịch với mức đột biến biến động nến sáng:
        atr_ratio_20d = 1.0 -> 0.10 Lot
        atr_ratio_20d = 1.5 -> 0.07 Lot
        atr_ratio_20d = 2.0 -> 0.05 Lot
        """
        if atr_ratio_20d <= 1.0:
            return round(self.base_lot, 2)

        raw_lot = self.base_lot / atr_ratio_20d
        lot = round(raw_lot, 2)
        lot = max(self.min_lot, min(self.max_lot, lot))
        return round(lot, 2)
