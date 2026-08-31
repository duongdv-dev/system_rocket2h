import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(BASE_DIR, "output", "dca_results_2023_2024.json")
UI_DIR = os.path.join(BASE_DIR, "ui")

df_cache = None

def ensure_backtest_executed():
    """Ensure backtest results exist before serving Web UI."""
    if not os.path.exists(OUTPUT_JSON):
        print("Backtest results JSON not found. Running backtest engine first...")
        from src.dca_backtester import DCABacktester
        workspace_dir = os.path.dirname(BASE_DIR)
        possible_paths = [
            [os.path.join(workspace_dir, "XAUUSD_2023_m1.csv"), os.path.join(workspace_dir, "XAUUSD_2024_m1.csv")],
            [os.path.join(BASE_DIR, "..", "XAUUSD_2023_m1.csv"), os.path.join(BASE_DIR, "..", "XAUUSD_2024_m1.csv")],
            ["/app/data/XAUUSD_2023_m1.csv", "/app/data/XAUUSD_2024_m1.csv"]
        ]
        selected_paths = None
        for path_set in possible_paths:
            if all(os.path.exists(p) for p in path_set):
                selected_paths = path_set
                break
        if not selected_paths:
            selected_paths = possible_paths[0]

        backtester = DCABacktester(
            data_paths=selected_paths,
            initial_balance=10000.0,
            default_lot=0.1,
            lot_usd_per_point=10.0,
            max_daily_loss_pct=10.0
        )
        logs, final_bal = backtester.run_backtest()
        backtester.export_results(logs, final_bal, OUTPUT_JSON)

def get_df_cache():
    global df_cache
    if df_cache is None:
        from src.dca_backtester import DCABacktester
        workspace_dir = os.path.dirname(BASE_DIR)
        possible_paths = [
            [os.path.join(workspace_dir, "XAUUSD_2023_m1.csv"), os.path.join(workspace_dir, "XAUUSD_2024_m1.csv")],
            [os.path.join(BASE_DIR, "..", "XAUUSD_2023_m1.csv"), os.path.join(BASE_DIR, "..", "XAUUSD_2024_m1.csv")],
            ["/app/data/XAUUSD_2023_m1.csv", "/app/data/XAUUSD_2024_m1.csv"]
        ]
        selected_paths = None
        for path_set in possible_paths:
            if all(os.path.exists(p) for p in path_set):
                selected_paths = path_set
                break
        if not selected_paths:
            selected_paths = possible_paths[0]
            
        bt = DCABacktester(selected_paths)
        df_cache = bt.load_and_preprocess_data()
    return df_cache

class DCAServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/summary":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if os.path.exists(OUTPUT_JSON):
                with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"error": "Results file not found."}).encode("utf-8"))
            return

        elif path == "/api/day_chart":
            date_str = query.get("date", [None])[0]
            if not date_str:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Date parameter missing")
                return

            try:
                df = get_df_cache()
                day_df = df[df["date_str"] == date_str].copy()

                if day_df.empty:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"No data for selected date")
                    return

                day_df['time_str'] = day_df['dt_ict'].dt.strftime('%H:%M')
                window_df = day_df[(day_df['time_str'] >= '09:30') & (day_df['time_str'] <= '12:30')].copy()

                candles = []
                for _, row in window_df.iterrows():
                    candles.append({
                        "time": int(row['dt_utc'].timestamp()),
                        "time_ict": row['dt_ict'].strftime('%H:%M:%S'),
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": float(row['close']),
                    })

                cand_10am = day_df[day_df['time_str'] >= '10:00'].iloc[0] if len(day_df[day_df['time_str'] >= '10:00']) > 0 else None
                anchor_price = float(cand_10am['open']) if cand_10am is not None else 0.0

                resp_data = {
                    "date": date_str,
                    "anchor_price": anchor_price,
                    "candles": candles
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(resp_data).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
            return

        super().do_GET()

def run_server(port=8000):
    ensure_backtest_executed()
    print("=" * 70)
    print(f"  🚀 DCA TRADING BACKTEST WEB UI DASHBOARD RUNNING")
    print(f"  --> Open Browser: http://localhost:{port}")
    print("=" * 70)
    server_address = ("", port)
    httpd = HTTPServer(server_address, DCAServerHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Web UI server...")

if __name__ == "__main__":
    run_server()
