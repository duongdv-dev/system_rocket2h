FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and UI files
COPY src/ ./src/
COPY ui/ ./ui/
COPY server.py .

EXPOSE 8000

# Default command runs Web UI server + backtest engine
CMD ["python", "server.py"]
