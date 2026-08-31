import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(BASE_DIR, "output", "dca_results_2023_2024.json")
UI_DIR = os.path.join(BASE_DIR, "ui")

df_cache = None

def export_dca_results(daily_logs, final_balance, output_path):
    df_logs = pd.DataFrame(daily_logs)
    traded_days = df_logs[df_logs['direction'] != 'NONE']
    tp_days = len(traded_days[traded_days['tp_hit'] == True])
    sl_days = len(traded_days[traded_days['sl_hit'] == True])
    loss_days = len(traded_days[traded_days['daily_pnl_usd'] < 0])

    initial_balance = 10000.0
    net_pnl = final_balance - initial_balance
    win_rate = (tp_days / len(traded_days) * 100) if len(traded_days) > 0 else 0.0
    max_dd_usd = df_logs['max_drawdown_usd'].max()
    max_dd_pct = (max_dd_usd / initial_balance) * 100.0

    summary = {
        "initial_balance_usd": initial_balance,
        "final_balance_usd": round(final_balance, 2),
        "total_pnl_usd": round(net_pnl, 2),
        "total_return_pct": round((net_pnl / initial_balance) * 100, 2),
        "base_lot": 0.40,
        "max_daily_loss_pct_cap": 20.0,
        "total_trading_days": len(traded_days),
        "tp_hit_days": tp_days,
        "sl_hit_days": sl_days,
        "loss_days": loss_days,
        "win_rate_pct": round(win_rate, 2),
        "max_drawdown_usd": round(max_dd_usd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2)
    }

    res_data = {
        "summary": summary,
        "daily_results": daily_logs
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(res_data, f, indent=4, ensure_ascii=False)
    print(f"Exported baseline DCA results to: {output_path}")

def run_dca_baseline_backtest():
    print("Running baseline DCA backtest with Base 0.40 Lot and 20.0% max daily loss cap...")
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
        default_lot=0.40,
        lot_usd_per_point=100.0,
        max_daily_loss_pct=20.0
    )
    logs, final_bal = backtester.run_backtest()
    export_dca_results(logs, final_bal, OUTPUT_JSON)

class DCADashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/api/summary':
            self.send_json_file(OUTPUT_JSON)
        elif parsed_path.path == '/api/day_chart':
            self.handle_day_chart_api(parsed_path.query)
        else:
            super().do_GET()

    def send_json_file(self, file_path):
        if not os.path.exists(file_path):
            run_dca_baseline_backtest()
            
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
        params = urllib.parse.parse_qs(query_str)
        date_str = params.get('date', [None])[0]

        if not date_str:
            self.send_error(400, "Missing date parameter")
            return

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

        try:
            bt = DCABacktester(selected_paths, default_lot=0.40, max_daily_loss_pct=20.0)
            full_df = bt.load_and_preprocess_data()
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

def run_server(port=8000):
    run_dca_baseline_backtest()
    server_address = ('', port)
    httpd = HTTPServer(server_address, DCADashboardHandler)
    print(f"Server running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
