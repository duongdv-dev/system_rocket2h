import os
import sys
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "src"))

from train_master_model import train_master_ai
from run_13step_evaluation import run_evaluation
from run_step_by_step_evaluation import run_step_by_step_evaluation

OUTPUT_DIR = os.path.join(base_dir, "output")
UI_DIR = os.path.join(base_dir, "ui")

REPORT_JSON = os.path.join(OUTPUT_DIR, "comparison_report.json")
RESULTS_JSON = os.path.join(OUTPUT_DIR, "filtered_results_2023_2025.json")
STEP_MATRIX_JSON = os.path.join(OUTPUT_DIR, "step_by_step_comparison_matrix.json")

def ensure_evaluation_executed():
    if not os.path.exists(os.path.join(OUTPUT_DIR, "ai_master_model.joblib")):
        print("Training Master AI Model...")
        train_master_ai()
    if not os.path.exists(REPORT_JSON):
        print("Running 13-Step System Evaluation...")
        run_evaluation()
    if not os.path.exists(STEP_MATRIX_JSON):
        print("Running Step-by-Step Matrix Evaluation (Step 0 -> Step 13)...")
        run_step_by_step_evaluation()

class Master13StepDashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/comparison':
            self.send_json_file(REPORT_JSON)
        elif parsed_path.path == '/api/summary':
            self.send_json_file(RESULTS_JSON)
        elif parsed_path.path == '/api/step_matrix':
            self.send_json_file(STEP_MATRIX_JSON)
        else:
            super().do_GET()

    def send_json_file(self, file_path):
        ensure_evaluation_executed()
        if os.path.exists(file_path):
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "JSON Report Not Found")

def run_server(port=8005):
    ensure_evaluation_executed()
    server_address = ('', port)
    httpd = HTTPServer(server_address, Master13StepDashboardHandler)
    print(f"🚀 Master 13-Step System Dashboard Server running at http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
