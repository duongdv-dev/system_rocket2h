import os
import sys
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

base_dir = current_dir
output_dir = os.path.join(base_dir, "output")
ui_dir = os.path.join(base_dir, "ui")

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="System Rocket 2H - Single-Trade 1% Target System Dashboard")

    if os.path.exists(ui_dir):
        app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def read_root():
        html_path = os.path.join(ui_dir, "index.html")
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>Single-Trade 1% Target System Dashboard</h1>"

    @app.get("/api/results")
    def get_results():
        json_path = os.path.join(output_dir, "single_trade_evaluation_2023_2025.json")
        if not os.path.exists(json_path):
            try:
                from evaluate_single_trade import evaluate_2023_2025
                evaluate_2023_2025()
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
                
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JSONResponse(content=data)
        else:
            return JSONResponse(status_code=404, content={"error": "Evaluation results not found."})

    @app.get("/api/meta")
    def get_meta():
        meta_path = os.path.join(output_dir, "ai_single_model_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"status": "No trained model meta found"}

    if __name__ == "__main__":
        print("🚀 Khởi chạy Web Server FastAPI trên cổng http://0.0.0.0:8005 ...")
        uvicorn.run(app, host="0.0.0.0", port=8005)

except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class SimpleDashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                html_path = os.path.join(ui_dir, "index.html")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if os.path.exists(html_path):
                    with open(html_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.wfile.write(b"<h1>Single-Trade 1% Target System Dashboard</h1>")
            elif self.path == "/api/results":
                json_path = os.path.join(output_dir, "single_trade_evaluation_2023_2025.json")
                if not os.path.exists(json_path):
                    try:
                        from evaluate_single_trade import evaluate_2023_2025
                        evaluate_2023_2025()
                    except Exception as e:
                        pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                if os.path.exists(json_path):
                    with open(json_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.wfile.write(b'{"error": "Evaluation results not found."}')
            elif self.path == "/api/meta":
                meta_path = os.path.join(output_dir, "ai_single_model_meta.json")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                if os.path.exists(meta_path):
                    with open(meta_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.wfile.write(b'{"status": "No trained model meta found"}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    if __name__ == "__main__":
        server_address = ("0.0.0.0", 8005)
        httpd = HTTPServer(server_address, SimpleDashboardHandler)
        print("🚀 Khởi chạy Web Server HTTP (Built-in Python) trên cổng http://0.0.0.0:8005 ...")
        httpd.serve_forever()

