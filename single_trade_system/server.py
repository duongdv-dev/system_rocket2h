import os
import sys
import json
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

app = FastAPI(title="System Rocket 2H - Single-Trade 1% Target System Dashboard")

base_dir = current_dir
output_dir = os.path.join(base_dir, "output")
ui_dir = os.path.join(base_dir, "ui")

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
        # Trigger evaluation if file does not exist yet
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
    uvicorn.run(app, host="0.0.0.0", port=8005)
