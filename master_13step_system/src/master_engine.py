import numpy as np

class Master13StepEngine:
    """
    Master Engine Đóng Gói 13 Bước AI Cho System Rocket 2H:
    Hỗ trợ tham số max_step (0 đến 13) và max_step=99 (Chế Độ Tinh Hoa Tối Ưu Kết Hợp).
    """
    def __init__(self, base_lot=0.60, min_lot=0.15, skip_threshold=0.36, safe_threshold=0.20):
        self.base_lot = base_lot
        self.min_lot = min_lot
        self.skip_threshold = skip_threshold
        self.safe_threshold = safe_threshold

    def compute_pre10_config(self, prob_risk, features, max_step=13):
        """
        Xử lý cấu hình trước 10:00 AM ICT tùy thuộc vào max_step được kích hoạt.
        """
        # Step 0: Baseline gốc (Không qua AI)
        if max_step == 0:
            return {
                "decision": "TRADE",
                "vol_mode": "BASELINE",
                "vol_multiplier": 1.0,
                "active_lot": self.base_lot,
                "entry_factor_buy": 1.0,
                "entry_factor_sell": 1.0,
                "dca_factor_buy": 1.0,
                "dca_factor_sell": 1.0,
                "reason": "⚙️ STEP 0 - BASELINE (Không AI)"
            }

        # BƯỚC 1: Trade / Skip Gatekeeper
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

        # CHẾ ĐỘ 99: TỈNH HOA TỐI ƯU KẾT HỢP (OPTIMAL COMBO: Step 1 + Step 2 + Step 7 + Step 8)
        if max_step == 99:
            if prob_risk < self.safe_threshold:
                vol_mode = "NORMAL"
                vol_multiplier = 1.0
            else:
                vol_mode = "CONSERVATIVE"
                ratio = (self.skip_threshold - prob_risk) / (self.skip_threshold - self.safe_threshold)
                vol_multiplier = round(0.25 + ratio * 0.50, 2)
            
            active_lot = round(self.base_lot * vol_multiplier, 2)
            active_lot = max(self.min_lot, min(self.base_lot, active_lot))

            range_to_atr = features.get("range_to_atr_ratio", 1.0)
            cont_dca = max(0.95, min(1.30, 0.9 + 0.3 * range_to_atr / 2.0))

            return {
                "decision": "TRADE",
                "vol_mode": vol_mode,
                "vol_multiplier": vol_multiplier,
                "active_lot": active_lot,
                "entry_factor_buy": 1.0, # Đặt Entry chuẩn 1.0x ATR tránh nhiễu
                "entry_factor_sell": 1.0,
                "dca_factor_buy": round(cont_dca, 2),
                "dca_factor_sell": round(cont_dca, 2),
                "reason": f"🌟 OPTIMAL COMBO MASTER: Vol={active_lot}L ({vol_mode}) | P={prob_risk*100:.1f}%"
            }

        # BƯỚC 2: Chọn mức Volume
        if max_step >= 2:
            if prob_risk < self.safe_threshold:
                vol_mode = "NORMAL"
                vol_multiplier = 1.0
            else:
                vol_mode = "CONSERVATIVE"
                ratio = (self.skip_threshold - prob_risk) / (self.skip_threshold - self.safe_threshold)
                vol_multiplier = round(0.25 + ratio * 0.50, 2)
            active_lot = round(self.base_lot * vol_multiplier, 2)
            active_lot = max(self.min_lot, min(self.base_lot, active_lot))
        else:
            vol_mode = "NORMAL"
            vol_multiplier = 1.0
            active_lot = self.base_lot

        # BƯỚC 3 & 4: Profile Entry & DCA Step rời rạc
        entry_factor_buy = 1.0
        entry_factor_sell = 1.0
        dca_factor_buy = 1.0
        dca_factor_sell = 1.0

        range_to_atr = features.get("range_to_atr_ratio", 1.0)
        atr_ratio_20d = features.get("atr_ratio_20d", 1.0)
        directional_intensity = features.get("directional_intensity", 0.5)
        morning_direction = features.get("morning_direction", 0)

        if max_step >= 3:
            if range_to_atr < 1.2:
                entry_factor_buy = entry_factor_sell = 0.8
            elif range_to_atr > 2.2:
                entry_factor_buy = entry_factor_sell = 1.2

        if max_step >= 4:
            if atr_ratio_20d > 1.3:
                dca_factor_buy = dca_factor_sell = 1.25

        if max_step >= 6:
            cont_entry = 1.0 / max(0.8, min(1.25, atr_ratio_20d))
            entry_factor_buy = entry_factor_sell = round(cont_entry, 2)

        if max_step >= 7:
            cont_dca = max(0.95, min(1.30, 0.9 + 0.3 * range_to_atr / 2.0))
            dca_factor_buy = dca_factor_sell = round(cont_dca, 2)

        if max_step >= 10:
            if morning_direction == 1 and directional_intensity > 0.6:
                entry_factor_buy = round(0.85 * max(0.8, 1.0 / atr_ratio_20d), 2)
                entry_factor_sell = round(1.15 * min(1.3, atr_ratio_20d), 2)
                dca_factor_buy = 1.0
                dca_factor_sell = 1.25
            elif morning_direction == -1 and directional_intensity > 0.6:
                entry_factor_sell = round(0.85 * max(0.8, 1.0 / atr_ratio_20d), 2)
                entry_factor_buy = round(1.15 * min(1.3, atr_ratio_20d), 2)
                dca_factor_sell = 1.0
                dca_factor_buy = 1.25

        if max_step >= 13:
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
            "reason": f"✅ BƯỚC {max_step} TRADE: Vol={active_lot}L ({vol_mode}) | P={prob_risk*100:.1f}%"
        }

    def evaluate_in_session_checkpoints(self, current_time, direction, positions, current_price, anchor_price, atr14, floating_pnl, max_allowed_loss_usd, max_step=13):
        """
        Xử lý Bước 5, 8, 9, 11, 12 thời gian thực trong phiên tùy thuộc max_step.
        """
        action = {"allow_dca": True, "early_exit": False, "tp_target_price": anchor_price, "reason": "HOLD"}

        if not positions or direction == "NONE":
            return action

        num_positions = len(positions)
        hours = current_time.hour
        minutes = current_time.minute

        # CHẾ ĐỘ 99: OPTIMAL COMBO (In-session Stop DCA & Early Exit 11h30)
        if max_step == 99:
            if num_positions >= 4 or (floating_pnl < 0 and abs(floating_pnl) >= 0.50 * max_allowed_loss_usd):
                action["allow_dca"] = False
                action["reason"] = "🛑 OPTIMAL COMBO - STOP DCA BREAKER"

            if hours == 11 and minutes >= 30 and minutes < 35:
                if floating_pnl < 0 and abs(floating_pnl) >= 0.65 * max_allowed_loss_usd:
                    action["early_exit"] = True
                    action["reason"] = "⚠️ OPTIMAL COMBO - EARLY EXIT 11H30"
            return action

        # BƯỚC 5: Allow / Stop DCA Breaker System
        if max_step >= 5:
            if num_positions >= 4 or (floating_pnl < 0 and abs(floating_pnl) >= 0.50 * max_allowed_loss_usd):
                action["allow_dca"] = False
                action["reason"] = "🛑 BƯỚC 5 - STOP DCA BREAKER"

        # BƯỚC 8 & 9: Multi-Checkpoint Early Exit
        if max_step >= 9:
            if hours == 10 and minutes >= 30 and minutes < 35:
                dist_pts = abs(current_price - anchor_price)
                if dist_pts > 3.0 * atr14:
                    action["allow_dca"] = False

        if max_step >= 8:
            if hours == 11 and minutes >= 30 and minutes < 35:
                if floating_pnl < 0 and abs(floating_pnl) >= 0.65 * max_allowed_loss_usd:
                    action["early_exit"] = True
                    action["reason"] = "⚠️ BƯỚC 8 - EARLY EXIT 11H30"

        # BƯỚC 11: Dynamic Breakeven TP tại 11:00
        if max_step >= 11:
            if hours == 11 and minutes >= 0 and minutes < 5:
                if num_positions >= 2:
                    avg_entry = np.mean([p['entry_price'] for p in positions])
                    action["tp_target_price"] = avg_entry
                    action["reason"] = "🎯 BƯỚC 11 - CHECKPOINT 11H00: Breakeven TP"

        # BƯỚC 12: Dynamic Reduced TP tại 11:30
        if max_step >= 12:
            if hours == 11 and minutes >= 30 and minutes < 35:
                if num_positions >= 2:
                    avg_entry = np.mean([p['entry_price'] for p in positions])
                    reduced_tp = avg_entry + 0.5 * (anchor_price - avg_entry)
                    action["tp_target_price"] = reduced_tp
                    action["reason"] = "🎯 BƯỚC 12 - CHECKPOINT 11H30: Reduced Dynamic TP"

        return action
