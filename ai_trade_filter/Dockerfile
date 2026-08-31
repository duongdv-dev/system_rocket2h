FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and UI files
COPY src/ ./src/
COPY ui/ ./ui/
COPY server.py .

EXPOSE 8002

# Default command runs Step 1 Training
CMD ["python", "src/train_filter.py"]
