# AI Dynamic Volume Optimizer (Port 8003)

Hệ thống AI Quản Trị Khối Lượng Vị Thế Động (**Dynamic Position Sizing Model**), tự động điều chỉnh Lot size của các ngày giao dịch theo bội số chuẩn `0.01 Lot` dựa trên mức độ rủi ro $P(\text{Risk})$ lúc 10:00 sáng ICT.

---

## 🚀 Hướng Dẫn Thực Thi Từng Bước Bằng Docker Compose

### 📌 BƯỚC 1: Training Mô Hình AI Volume Optimizer (2020 - 2023)
Mở Terminal trong thư mục `ai_volume_optimizer` và gõ:
```bash
cd ai_volume_optimizer
docker compose run --rm --build volume_train
```

---

### 📌 BƯỚC 2: Backtest Dynamic Volume (2023 - 2024) & Mở Web UI (Port 8003)
Gõ tiếp lệnh:
```bash
docker compose up volume_web --build
```
Mở trình duyệt truy cập: **`http://localhost:8003`** (hoặc `http://66.154.127.117:8003/`) để quan sát kết quả tối ưu khối lượng vị thế!
