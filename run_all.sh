#!/bin/bash
set -e

echo "=========================================================================="
echo "🚀 SYSTEM ROCKET 2H - KHỞI CHẠY TOÀN BỘ HỆ THỐNG GIAO DỊCH TỰ ĐỘNG"
echo "=========================================================================="

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo ""
echo "📌 [BƯỚC 1/2]: HUẤN LUYỆN TOÀN BỘ MÔ HÌNH AI & BACKTEST OUT-OF-SAMPLE (2023-2024)..."

echo "  -> Running AI Risk Filter (Giai đoạn 2)..."
docker compose -f ai_trade_filter/docker-compose.yml run --rm ai_train
docker compose -f ai_trade_filter/docker-compose.yml run --rm ai_train python src/compare_results.py

echo "  -> Running AI Dynamic Volume (Giai đoạn 3)..."
docker compose -f ai_volume_optimizer/docker-compose.yml run --rm volume_train
docker compose -f ai_volume_optimizer/docker-compose.yml run --rm volume_train python src/compare_volume_results.py

echo "  -> Running Master System 13-Step AI (Cổng 8005)..."
docker compose -f master_13step_system/docker-compose.yml run --rm master_13step_web python src/train_master_model.py
docker compose -f master_13step_system/docker-compose.yml run --rm master_13step_web python src/run_13step_evaluation.py

echo ""
echo "📌 [BƯỚC 2/2]: KHỞI CHẠY DOCKER DASHBOARDS TRÊN CÁC PORT..."
docker compose up -d --build

echo ""
echo "=========================================================================="
echo "🎉 TẤT CẢ 5 BẢNG ĐIỀU KHIỂN WEB UI ĐÃ SẴN SÀNG:"
echo "=========================================================================="
echo "  1. DCA Baseline Dashboard    : http://localhost:8000"
echo "  2. AI Risk Filter Dashboard  : http://localhost:8002"
echo "  3. Dynamic Volume Dashboard   : http://localhost:8003"
echo "  4. Master System 3-Layer UI  : http://localhost:8004"
echo "  5. Master 13-Step AI UI      : http://localhost:8005"
echo "=========================================================================="
