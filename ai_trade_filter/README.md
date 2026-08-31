# AI Daily Trade Risk Filter (Train 2020-2023 -> Backtest 2023-2024)

Hệ thống AI Machine Learning tự động phân tích các chỉ số thị trường tính đến 10:00 sáng ICT để **phát hiện và BỎ QUA KHÔNG GIAO DỊCH (NO TRADE)** những ngày có nguy cơ thua lỗ nặng hoặc dính Cắt Lỗ 10%.

---

## 🚀 Hướng Dẫn Thực Thi Bằng Docker Compose (Từng Bước)

### 📌 BƯỚC 1: Chạy Training Mô Hình AI (2020 - 2023)
Mở Terminal trong thư mục `ai_trade_filter` và gõ:
```bash
cd ai_trade_filter
docker compose run --rm --build ai_train
```
Lệnh này sẽ:
- Rebuild container với đầy đủ file mã nguồn mới nhất.
- Nạp 4 năm dữ liệu 2020 - 2023 (`XAUUSD_2020_m1.csv` đến `2023_m1.csv`).
- Gắn nhãn `trade` / `skip` cho 1,000+ ngày lịch sử và lưu tại `output/labeled_training_days_2020_2023.csv`.
- Huấn luyện mô hình AI `RandomForestClassifier` (300 cây) và xuất file mô hình `output/ai_risk_model.joblib`.

---

### 📌 BƯỚC 2: Chạy Backtest Out-of-Sample (2023 - 2024) & Mở Web UI
Sau khi Bước 1 hoàn tất, gõ tiếp lệnh:
```bash
docker compose up ai_web --build
```
Lệnh này sẽ:
- Áp dụng mô hình AI `ai_risk_model.joblib` vừa học ở Bước 1 vào tập test 2023 - 2024.
- Khởi chạy Web UI Server trên cổng **8002**.
- Mở trình duyệt truy cập: **`http://localhost:8002`** để xem kết quả!
