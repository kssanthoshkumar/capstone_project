# Dockerfile — Network Anomaly Detection API
# Builds a production-ready FastAPI container serving the XGBoost model.
#
# Build:  docker build -t anomaly-detector .
# Run:    docker run -p 8000:8000 anomaly-detector
# Test:   curl http://localhost:8000/health -H "X-From: docker-test"

FROM python:3.11-slim

# Security: run as non-root
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# Install dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy source and artefacts
COPY src/ ./src/
COPY models/preprocessor.pkl models/xgboost.pkl models/configs.yaml ./models/
COPY train_and_save.py .

# If model artefacts are absent at build time, train inside the container
# (requires data/raw/ to be mounted or auto-downloaded)
RUN python -c "import os; \
    missing = not (os.path.exists('models/xgboost.pkl') and os.path.exists('models/preprocessor.pkl')); \
    print('Models present.' if not missing else 'WARNING: model files missing — mount or run train_and_save.py')"

# Expose API port
EXPOSE 8000

# Health check (Docker will restart if /health fails)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

USER appuser

# Start FastAPI with Uvicorn
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
