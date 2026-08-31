# Master System Dashboard (Port 8004)

Hệ thống Master System phối hợp HOÀN HẢO CẢ 3 LỚP CHIẾN LƯỢC:
1. **Lớp 1**: AI Risk Filter + Hard Daily Loss Cap 5% (-$500 USD).
2. **Lớp 2**: AI Dynamic Volume Scaling ($V_{day} \in [0.00, 0.10]$ Lot).
3. **Lớp 3**: Adaptive Step Size Optimization ($\text{Step}_{day} \in [0.50 \times \text{ATR}, 1.00 \times \text{ATR}]$).

---

## 🚀 Hướng Dẫn Thực Thi Từng Bước Bằng Docker Compose

### 📌 BƯỚC 1: Training Mô Hình AI Master System (2020 - 2023)
Mở Terminal trong thư mục `ai_step_optimizer` và gõ:
```bash
cd ai_step_optimizer
docker compose run --rm --build master_train
```

---

### 📌 BƯỚC 2: Backtest Master System (2023 - 2024) & Mở Web UI (Port 8004)
Gõ tiếp lệnh:
```bash
docker compose up master_web --build
```
Mở trình duyệt truy cập: **`http://localhost:8004`** (hoặc `http://66.154.127.117:8004/`) để quan sát kết quả phối hợp 3 lớp!
