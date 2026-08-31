# DCA Trading System (2023 - 2024 Backtest & Web UI Dashboard)

Hệ thống backtest chiến lược DCA Intraday trên cặp XAUUSD cho 2 năm 2023 và 2024, tích hợp **Giao diện Web UI TradingView Visualizer** và **Script tự động đối soát logic**.

---

## 📌 Quy Trình Chiến Lược (Trading Strategy)

1. **Khung thời gian (ICT / UTC+7)**:
   - **Mốc lấy giá chuẩn**: 10:00 sáng Việt Nam.
   - **Mốc đóng lệnh bắt buộc**: 12:00 trưa Việt Nam.
2. **Giá mốc & Bước giá DCA**:
   - **Anchor Price ($P_0$)**: Giá mở cửa (Open) nến 10:00 sáng.
   - **DCA Step ($S$)**: Chỉ số ATR(14) khung nến M5 tính đến 10:00 sáng.
3. **Quy tắc khớp lệnh ("Khớp bên nào đánh bên đó")**:
   - Volume mặc định: `0.1 lot` ($1.0$ giá biến động = $\pm 10$ USD PnL).
   - **BUY**: Nếu giá chạm $P_0 - S$, mở BUY 1. Nhồi tiếp BUY 2 tại $P_0 - 2S$, BUY 3 tại $P_0 - 3S$,...
   - **SELL**: Nếu giá chạm $P_0 + S$, mở SELL 1. Nhồi tiếp SELL 2 tại $P_0 + 2S$, SELL 3 tại $P_0 + 3S$,...
   - **Take Profit (TP)**: TP của TẤT CẢ các lệnh đang mở đặt tại $P_0$.
   - **Stop Loss (SL - Cắt lỗ tối đa 10%)**: Nếu tổng lỗ trạng thái vượt mức **10% vốn ban đầu của ngày**, hệ thống đóng tất cả lệnh ngay lập tức và dừng giao dịch ngày hôm đó.
   - **Quy tắc 1 chu kỳ/ngày ("Nghỉ luôn")**: Khi chu kỳ giao dịch kết thúc (TP, SL 10%, hoặc bị đóng lúc 12h00), hệ thống dừng giao dịch cho đến hết ngày.
4. **Cắt lệnh cưỡng chế lúc 12:00 trưa**:
   - Nếu chưa TP hoặc SL lúc 12:00 trưa, đóng tất cả vị thế theo giá thị trường lúc 12:00.

---

## 🖥️ Hướng Dẫn Khởi Chạy Web UI Dashboard

### Cách 1: Khởi chạy bằng Docker Compose (Khuyên dùng)
```bash
# Di chuyển vào thư mục dca_system
cd dca_system

# Build và mở Web UI Dashboard
docker compose up --build
```
Mở trình duyệt truy cập: **`http://localhost:8000`**

---

### Cách 2: Khởi chạy trực tiếp bằng Python
```bash
# Cài đặt các thư viện cần thiết
pip install -r dca_system/requirements.txt

# Chạy Web UI Server
python3 dca_system/server.py
```
Mở trình duyệt truy cập: **`http://localhost:8000`**

---

## 🔍 Chạy Script Tự Động Kiểm Tra Logic (Audit Script)

Để kiểm tra và đối soát tự động 100% tính đúng đắn của logic backtest với dữ liệu nến thô CSV:
```bash
python3 dca_system/src/verify_logic.py
```

---

## 📊 Cấu Trúc Kết Quả JSON (`output/dca_results_2023_2024.json`)

File JSON lưu kết quả chi tiết từng ngày giao dịch và tổng kết toàn bộ 2 năm tại `dca_system/output/dca_results_2023_2024.json`.
