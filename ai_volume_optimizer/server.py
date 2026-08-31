import os
import sys
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "src"))

from feature_extractor import FeatureExtractor
from compare_volume_results import run_volume_optimization_comparison

OUTPUT_DIR = os.path.join(base_dir, "output")
UI_DIR = os.path.join(base_dir, "ui")
DATA_DIR = os.path.dirname(base_dir)

REPORT_JSON = os.path.join(OUTPUT_DIR, "comparison_report.json")
RESULTS_JSON = os.path.join(OUTPUT_DIR, "filtered_results_2023_2024.json")

def ensure_volume_backtest_executed():
    """Luôn thực thi Backtest Dynamic Volume để cập nhật báo cáo mới nhất."""
    print("Executing Dynamic Volume Optimization Backtest (2023-2024)...")
    try:
        run_volume_optimization_comparison()
    except Exception as e:
        print(f"Error running volume comparison: {e}")

class VolumeDashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/comparison':
            self.send_json_file(REPORT_JSON)
        elif parsed_path.path == '/api/summary':
            self.send_json_file(RESULTS_JSON)
        elif parsed_path.path == '/api/day_chart':
            self.handle_day_chart_api(parsed_path.query)
        else:
            super().do_GET()

    def send_json_file(self, file_path):
        if not os.path.exists(file_path):
            ensure_volume_backtest_executed()
            
        if os.path.exists(file_path):
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "JSON Report Not Found")

    def handle_day_chart_api(self, query_str):
        params = parse_qs(query_str)
        date_str = params.get('date', [None])[0]

        if not date_str:
            self.send_error(400, "Missing date parameter")
            return

        possible_path_sets = [
            [
                os.path.join(DATA_DIR, "XAUUSD_2023_m1.csv"),
                os.path.join(DATA_DIR, "XAUUSD_2024_m1.csv")
            ],
            [
                os.path.join(base_dir, "..", "XAUUSD_2023_m1.csv"),
                os.path.join(base_dir, "..", "XAUUSD_2024_m1.csv")
            ],
            [
                "/app/data/XAUUSD_2023_m1.csv",
                "/app/data/XAUUSD_2024_m1.csv"
            ]
        ]

        test_files = None
        for path_set in possible_path_sets:
            if all(os.path.exists(p) for p in path_set):
                test_files = path_set
                break

        if not test_files:
            self.send_error(404, "Test CSV files not found")
            return

        try:
            extractor = FeatureExtractor(test_files)
            full_df = extractor.load_data()
            day_m1 = full_df[full_df['date_str'] == date_str].copy()

            if day_m1.empty:
                self.send_error(404, f"No M1 data found for date {date_str}")
                return

            candles = []
            for _, row in day_m1.iterrows():
                candles.append({
                    "time": int(row['dt_utc'].timestamp()),
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

            anchor_row = day_m1[day_m1['time'] >= day_m1['time'].min()]
            anchor_price = float(anchor_row.iloc[0]['open']) if not anchor_row.empty else 0.0

            response_data = {
                "date": date_str,
                "anchor_price": anchor_price,
                "candles": candles
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            print(f"Error serving day chart: {e}")
            self.send_error(500, str(e))

def run_server(port=8003):
    ensure_volume_backtest_executed()
    server_address = ('', port)
    httpd = HTTPServer(server_address, VolumeDashboardHandler)
    print(f"\n==================================================================")
    print(f"🚀 AI Dynamic Volume Optimizer Dashboard Running on Port {port}")
    print(f"👉 Open in browser: http://localhost:{port}")
    print(f"==================================================================\n")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
