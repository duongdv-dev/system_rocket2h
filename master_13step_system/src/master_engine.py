import numpy as np

class Master13StepEngine:
    """
    Master Engine Đóng Gói 13 Bước AI Cho System Rocket 2H:
    - Step 1: Trade / Skip (Gatekeeper)
    - Step 2: Volume Multiplier (SKIP, CONSERVATIVE, NORMAL)
    - Step 3: Entry Profile (Near / Standard / Far)
    - Step 4: DCA Step Profile (Standard / Wide)
    - Step 5: Dynamic DCA Breaker (Allow / Stop DCA in-session)
    - Step 6 & 7: Continuous Entry & DCA Range Tuning
    - Step 8 & 9: Multi-Checkpoint Early Exit (10h30, 11h00, 11h30)
    - Step 10: Asymmetric Buy / Sell Tuning
    - Step 11 & 12: Dynamic & Reduced TP Target
    - Step 13: Master Pruner (Kháng Overfitting)
    """
    def __init__(self, base_lot=0.60, min_lot=0.15, skip_threshold=0.36, safe_threshold=0.20):
        self.base_lot = base_lot
        self.min_lot = min_lot
        self.skip_threshold = skip_threshold
        self.safe_threshold = safe_threshold

    def compute_pre10_config(self, prob_risk, features):
        """
        Xử lý Bước 1 đến Bước 4, 6, 7, 10 lúc 10h00 AM ICT
        """
        # BƯỚC 1: Trade / Skip
        if prob_risk >= self.skip_threshold:
            return {
                "decision": "SKIP",
                "vol_multiplier": 0.0,
                "active_lot": 0.0,
                "entry_factor_buy": 1.0,
                "entry_factor_sell": 1.0,
                "dca_factor_buy": 1.0,
                "dca_factor_sell": 1.0,
                "reason": f"🛑 BƯỚC 1 - BỎ QUA (SKIP): P={prob_risk*100:.1f}% ≥ {self.skip_threshold*100:.1f}%"
            }

        # BƯỚC 2: Chọn mức Volume
        if prob_risk < self.safe_threshold:
            vol_mode = "NORMAL"
            vol_multiplier = 1.0
        else:
            vol_mode = "CONSERVATIVE"
            # Tối ưu hệ số k liên tục k in [0.25, 0.75]
            ratio = (self.skip_threshold - prob_risk) / (self.skip_threshold - self.safe_threshold)
            vol_multiplier = round(0.25 + ratio * 0.50, 2)

        active_lot = round(self.base_lot * vol_multiplier, 2)
        active_lot = max(self.min_lot, min(self.base_lot, active_lot))

        # BƯỚC 3, 4, 6, 7: Profile & Continuous Range Entry / DCA
        directional_intensity = features.get("directional_intensity", 0.5)
        morning_direction = features.get("morning_direction", 0)
        atr_ratio_20d = features.get("atr_ratio_20d", 1.0)

        # BƯỚC 10: Tách riêng tham số Buy / Sell phi đối xứng theo Trend sáng
        if morning_direction == 1 and directional_intensity > 0.6:
            # Sáng tăng mạnh: Chờ Buy gần hơn, Sell xa hơn để tránh hứng bão
            entry_factor_buy = round(0.85 * max(0.8, 1.0 / atr_ratio_20d), 2)
            entry_factor_sell = round(1.15 * min(1.3, atr_ratio_20d), 2)
            dca_factor_buy = 1.0
            dca_factor_sell = 1.25 # Wide DCA cho Sell
        elif morning_direction == -1 and directional_intensity > 0.6:
            # Sáng giảm mạnh: Chờ Sell gần hơn, Buy xa hơn
            entry_factor_sell = round(0.85 * max(0.8, 1.0 / atr_ratio_20d), 2)
            entry_factor_buy = round(1.15 * min(1.3, atr_ratio_20d), 2)
            dca_factor_sell = 1.0
            dca_factor_buy = 1.25 # Wide DCA cho Buy
        else:
            # Thị trường đi ngang / Range chuẩn
            entry_factor_buy = 1.0
            entry_factor_sell = 1.0
            dca_factor_buy = 1.0
            dca_factor_sell = 1.0

        # BƯỚC 13: Tinh giản tham số (Pruning) đảm bảo tính tổng quát
        entry_factor_buy = max(0.75, min(1.30, entry_factor_buy))
        entry_factor_sell = max(0.75, min(1.30, entry_factor_sell))
        dca_factor_buy = max(0.90, min(1.35, dca_factor_buy))
        dca_factor_sell = max(0.90, min(1.35, dca_factor_sell))

        return {
            "decision": "TRADE",
            "vol_mode": vol_mode,
            "vol_multiplier": vol_multiplier,
            "active_lot": active_lot,
            "entry_factor_buy": entry_factor_buy,
            "entry_factor_sell": entry_factor_sell,
            "dca_factor_buy": dca_factor_buy,
            "dca_factor_sell": dca_factor_sell,
            "reason": f"✅ BƯỚC 1-13 MASTER TRADE: Vol={active_lot}L ({vol_mode}) | P={prob_risk*100:.1f}%"
        }

    def evaluate_in_session_checkpoints(self, current_time, direction, positions, current_price, anchor_price, atr14, floating_pnl, max_allowed_loss_usd):
        """
        Xử lý Bước 5, 8, 9, 11, 12 thời gian thực trong phiên (10:00 - 12:00 ICT)
        """
        action = {"allow_dca": True, "early_exit": False, "tp_target_price": anchor_price, "reason": "HOLD"}

        if not positions or direction == "NONE":
            return action

        num_positions = len(positions)
        hours = current_time.hour
        minutes = current_time.minute

        # BƯỚC 5: Allow / Stop DCA Breaker System
        # Ngắt DCA khẩn cấp nếu dính 4 tầng trở lên hoặc âm vượt 50% Daily Cap
        if num_positions >= 4 or (floating_pnl < 0 and abs(floating_pnl) >= 0.50 * max_allowed_loss_usd):
            action["allow_dca"] = False
            action["reason"] = "🛑 BƯỚC 5 - STOP DCA BREAKER: Tải vị thế quá lớn"

        # BƯỚC 8, 9: Checkpoint đánh giá tại 10:30, 11:00, 11:30
        if hours == 10 and minutes >= 30 and minutes < 35:
            # Checkpoint 10h30: Nếu đi ngược quá 3 ATR mà chưa có dấu hiệu hồi quay -> Ngắt nhồi lệnh thêm
            dist_pts = abs(current_price - anchor_price)
            if dist_pts > 3.0 * atr14:
                action["allow_dca"] = False

        elif hours == 11 and minutes >= 0 and minutes < 5:
            # Checkpoint 11h00: BƯỚC 11 - Kéo TP về Breakeven (Hoàn vốn) nếu đã nhồi >= 2 lệnh
            if num_positions >= 2:
                avg_entry = np.mean([p['entry_price'] for p in positions])
                action["tp_target_price"] = avg_entry # Kéo TP về BE
                action["reason"] = "🎯 BƯỚC 11 - CHECKPOINT 11H00: Kéo TP về Breakeven"

        elif hours == 11 and minutes >= 30 and minutes < 35:
            # Checkpoint 11h30: BƯỚC 12 - Dynamic Reduced TP (Thu hẹp TP 50% đoạn đường)
            if num_positions >= 2:
                avg_entry = np.mean([p['entry_price'] for p in positions])
                reduced_tp = avg_entry + 0.5 * (anchor_price - avg_entry)
                action["tp_target_price"] = reduced_tp
                action["reason"] = "🎯 BƯỚC 12 - CHECKPOINT 11H30: Reduced Dynamic TP"

            # Nếu âm nặng gần mốc 12h -> Early Exit sớm để cắt lỗ nhỏ thay vì dính 12h
            if floating_pnl < 0 and abs(floating_pnl) >= 0.65 * max_allowed_loss_usd:
                action["early_exit"] = True
                action["reason"] = "⚠️ BƯỚC 8&9 - EARLY EXIT 11H30: Cắt lỗ sớm bảo vệ vốn"

        return action
