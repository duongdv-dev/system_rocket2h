#!/bin/bash
set -e

echo "=========================================================================="
echo "🚀 SYSTEM ROCKET 2H - KHỞI CHẠY TOÀN BỘ HỆ THỐNG GIAO DỊCH TỰ ĐỘNG"
echo "=========================================================================="

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo ""
echo "📌 [BƯỚC 1/2]: HUẤN LUYỆN TOÀN BỘ MÔ HÌNH AI (2020 - 2023)..."

echo "  -> Training AI Risk Filter (Giai đoạn 2)..."
docker compose -f ai_trade_filter/docker-compose.yml run --rm ai_train

echo "  -> Training AI Dynamic Volume (Giai đoạn 3)..."
docker compose -f ai_volume_optimizer/docker-compose.yml run --rm volume_train

echo "  -> Training Master System 3-Layer (Giai đoạn 4)..."
docker compose -f ai_step_optimizer/docker-compose.yml run --rm master_train

echo ""
echo "📌 [BƯỚC 2/2]: KHỞI CHẠY DOCKER DASHBOARDS TRÊN CÁC PORT..."
docker compose up -d --build

echo ""
echo "=========================================================================="
echo "🎉 TẤT CẢ 4 BẢNG ĐIỀU KHIỂN WEB UI ĐÃ SẴN SÀNG:"
echo "=========================================================================="
echo "  1. DCA Baseline Dashboard   : http://localhost:8000 (hoặc http://66.154.127.117:8000/)"
echo "  2. AI Risk Filter Dashboard : http://localhost:8002 (hoặc http://66.154.127.117:8002/)"
echo "  3. Dynamic Volume Dashboard  : http://localhost:8003 (hoặc http://66.154.127.117:8003/)"
echo "  4. Master System Dashboard  : http://localhost:8004 (hoặc http://66.154.127.117:8004/)"
echo "=========================================================================="
