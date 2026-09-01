#!/bin/bash
set -e

echo "=========================================================================="
echo "🚀 SYSTEM ROCKET 2H - SCRIPT CHẠY BACKTEST TOÀN BỘ VÀ TỰ ĐỘNG PUSH GIT"
echo "=========================================================================="

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo ""
echo "📌 [BƯỚC 1/2]: THỰC THI HUẤN LUYỆN AI VÀ XUẤT BÁO CÁO 4 CHIẾN LƯỢC..."

echo "  -> 1/4: Backtesting Baseline DCA System (Port 8000)..."
docker compose -f dca_system/docker-compose.yml run --rm dca_app python server.py || true

echo "  -> 2/4: Training & Backtesting AI Risk Filter (Port 8002)..."
docker compose -f ai_trade_filter/docker-compose.yml run --rm ai_train
docker compose -f ai_trade_filter/docker-compose.yml run --rm ai_train python src/compare_results.py

echo "  -> 3/4: Training & Backtesting AI Dynamic Volume (Port 8003)..."
docker compose -f ai_volume_optimizer/docker-compose.yml run --rm volume_train
docker compose -f ai_volume_optimizer/docker-compose.yml run --rm volume_train python src/compare_volume_results.py

echo "  -> 4/4: Training & Backtesting Master System (Port 8004)..."
docker compose -f ai_step_optimizer/docker-compose.yml run --rm master_train
docker compose -f ai_step_optimizer/docker-compose.yml run --rm master_train python src/compare_step_results.py

echo ""
echo "📌 [BƯỚC 2/2]: TỰ ĐỘNG COMMIT VÀ PUSH TOÀN BỘ KẾT QUẢ MỚI LÊN GITHUB..."
git add .
git commit -m "Auto update trained AI models and high-yield backtest results" || echo "No new changes to commit."
git push origin main

echo ""
echo "=========================================================================="
echo "🎉 HOÀN THÀNH TẤT CẢ BACKTEST VÀ ĐÃ PUSH LÊN GITHUB NGHỆ THUẬT!"
echo "=========================================================================="
echo "  Bây giờ bạn chỉ cần mở Terminal ở máy Local và gõ: git pull"
echo "=========================================================================="
