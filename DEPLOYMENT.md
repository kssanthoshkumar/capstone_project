# Deployment Guide — Network Anomaly Detection

This guide covers local deployment of the FastAPI inference API and the Streamlit UI, the retraining pipeline, and the MLOps practices adopted in this project.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | ≥ 3.11 | Tested on 3.11 and 3.12 |
| pip | ≥ 23 | Bundled with Python |
| RAM | ≥ 4 GB | Required for XGBoost inference |
| Disk | ≥ 500 MB | Data + model artefacts |

---

## 1. Installation

```bash
# Clone the repository
git clone https://github.com/[your-username]/network-anomaly-detection.git
cd network-anomaly-detection

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# Install all dependencies
pip install -r requirements.txt
```

---

## 2. Train the Model (first-time setup)

The training script downloads NSL-KDD automatically if the raw files are absent, trains XGBoost, and saves all artefacts to `models/`.

```bash
python train_and_save.py
```

Expected output:
```
[1/3] Loading NSL-KDD dataset...
      Train: (125973, 42)  |  Test: (22544, 42)
[2/3] Preprocessing...
[3/3] Training XGBoost ...
      Test F1=0.9930  AUC-ROC=0.9990
✅  Training complete. Artifacts saved to models/
    Start the API with:  uvicorn src.app:app --port 8000
```

Saved artefacts:

| File | Description |
|------|-------------|
| `models/xgboost.pkl` | Best model (XGBoost) |
| `models/preprocessor.pkl` | Fitted ColumnTransformer |
| `models/configs.yaml` | Hyperparameters + metadata |
| `data/processed/*.npy` | Pre-split arrays for notebooks |

---

## 3. Running the FastAPI Inference API

```bash
uvicorn src.app:app --host 0.0.0.0 --port 8000
```

The server starts at `http://localhost:8000`.  Interactive docs are available at `http://localhost:8000/docs`.

### 3.1 Health Check

```bash
curl -X GET http://localhost:8000/health \
     -H "X-From: deployment-guide"
```

Expected response:
```json
{"status": "ok", "model_loaded": true, "preprocessor_loaded": true}
```

### 3.2 Single Prediction

```bash
curl -X POST http://localhost:8000/predict \
     -H "Content-Type: application/json" \
     -H "X-From: deployment-guide" \
     -d '{
       "duration": 0, "protocol_type": "tcp", "service": "http", "flag": "S0",
       "src_bytes": 0, "dst_bytes": 0, "land": 0, "wrong_fragment": 0,
       "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 0,
       "num_compromised": 0, "root_shell": 0, "su_attempted": 0,
       "num_root": 0, "num_file_creations": 0, "num_shells": 0,
       "num_access_files": 0, "num_outbound_cmds": 0,
       "is_host_login": 0, "is_guest_login": 0,
       "count": 511, "srv_count": 511,
       "serror_rate": 1.0, "srv_serror_rate": 1.0,
       "rerror_rate": 0.0, "srv_rerror_rate": 0.0,
       "same_srv_rate": 1.0, "diff_srv_rate": 0.0,
       "srv_diff_host_rate": 0.0, "dst_host_count": 255,
       "dst_host_srv_count": 255, "dst_host_same_srv_rate": 1.0,
       "dst_host_diff_srv_rate": 0.0, "dst_host_same_src_port_rate": 1.0,
       "dst_host_srv_diff_host_rate": 0.0, "dst_host_serror_rate": 1.0,
       "dst_host_srv_serror_rate": 1.0, "dst_host_rerror_rate": 0.0,
       "dst_host_srv_rerror_rate": 0.0
     }'
```

Expected response (DoS — Neptune attack):
```json
{"prediction": 1, "label": "attack", "probability": 0.9981}
```

### 3.3 Batch Prediction

```bash
curl -X POST http://localhost:8000/predict/batch \
     -H "Content-Type: application/json" \
     -H "X-From: deployment-guide" \
     -d '{"records": [<record_1>, <record_2>]}'
```

> **Note:** `X-From` header is required on all requests for traceability. Requests without it return HTTP 400.

---

## 4. Running the Streamlit UI

```bash
streamlit run src/ui.py
```

Opens at `http://localhost:8501`.

**Features:**
- Preset traffic scenarios (Normal HTTP, Port Scan, DoS Attack)
- Full 41-feature input form
- Real-time prediction with attack probability gauge
- 🤖 AI Analyst Explanation (requires `OPENAI_API_KEY` — see step 5)

---

## 5. GenAI Analyst Explanations (Optional)

Copy `.env.example` to `.env` and add your OpenAI API key:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

Restart the Streamlit UI.  The **"🤖 AI Analyst Explanation"** panel will now generate plain-English security briefings after each prediction.

---

## 6. Retraining the Model

Run `train_and_save.py` at any time to retrain on updated data.  The script overwrites `models/xgboost.pkl` and `models/preprocessor.pkl`.

```bash
# Retrain on the default NSL-KDD data
python train_and_save.py

# Recommended: point to a newer dataset (e.g. CICIDS-2017) by placing
# the CSV in data/raw/ and updating src/data_loader.py accordingly.
```

The running FastAPI server picks up new artefacts automatically on its next restart:

```bash
# Graceful restart (Uvicorn reloads on file change in dev mode)
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## 7. MLOps Practices

### 7.1 Model Versioning

All hyperparameters and the `best_model` identifier are persisted in `models/configs.yaml` at the end of every training run.  Before retraining in production, snapshot the current artefacts:

```bash
# Snapshot before retraining
cp -r models/ models_backup_$(date +%Y%m%d)/
python train_and_save.py
```

### 7.2 Reproducibility

| Practice | Implementation |
|----------|---------------|
| Fixed random seed | `random_seed: 42` in `configs.yaml` |
| Pinned dependencies | `requirements.txt` with `>=` lower bounds |
| Saved preprocessor | `models/preprocessor.pkl` ensures identical transforms at inference |
| Saved processed splits | `data/processed/*.npy` for notebook reproducibility |

### 7.3 Monitoring & Drift Detection

The `/health` endpoint provides a liveness signal suitable for uptime monitors (e.g. UptimeRobot, Prometheus blackbox exporter).

For **data drift detection** in production, integrate [Evidently AI](https://www.evidentlyai.com/):

```python
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset
import pandas as pd

report = Report(metrics=[DataDriftPreset()])
report.run(reference_data=reference_df, current_data=production_df)
report.save_html("reports/drift_report.html")
```

Recommended retraining trigger: retrain when the dataset drift score exceeds 0.1 on any of the top-10 SHAP features, or quarterly — whichever comes first.

### 7.4 Logging

The FastAPI app uses Python's standard `logging` module at `INFO` level.  All prediction requests log the `X-From` header for auditability.  In production, pipe logs to a SIEM:

```bash
uvicorn src.app:app --port 8000 2>&1 | tee -a logs/api.log
```

### 7.5 Security Controls

| Control | Implementation |
|---------|---------------|
| Input validation | Pydantic with range constraints on all 41 features |
| Injection prevention | No raw SQL or shell execution anywhere in the stack |
| Request traceability | `X-From` header required on every API call |
| Secret management | `OPENAI_API_KEY` via `.env` / environment — never hardcoded |
| Payload isolation | Model operates on metadata only; no network payload content read |

---

## 8. Demo

> **Recording the demo (GIF/screencast):**
>
> 1. Start the Streamlit UI: `streamlit run src/ui.py`
> 2. Select the **"DoS Attack (Neptune)"** preset from the sidebar
> 3. Click **"🔍 Analyse Traffic"**
> 4. Show the ⚠️ ATTACK DETECTED result and probability gauge
> 5. Expand **"🤖 AI Analyst Explanation"** to show the LLM briefing
> 6. Switch preset to **"Normal HTTP Traffic"** and repeat
>
> Recommended tool: [Kap](https://getkap.co/) (macOS) or [ShareX](https://getsharex.com/) (Windows) for GIF export.

Place the recorded file at `reports/demo.gif` and link it in `README.md`:

```markdown
![Demo](reports/demo.gif)
```

---

## 9. Project Structure Reference

```
capstone/
├── src/
│   ├── app.py                  # FastAPI REST API
│   ├── ui.py                   # Streamlit interactive UI
│   ├── genai_explainer.py      # LLM analyst explanation module
│   ├── models.py               # Model training + evaluation
│   ├── preprocessor.py         # Feature pipeline
│   ├── data_loader.py          # NSL-KDD loader
│   ├── feature_engineering.py  # Domain features + PCA
│   ├── explainability.py       # SHAP + LIME
│   └── bias_audit.py           # Fairness audit
├── models/
│   ├── xgboost.pkl             # Best model artefact
│   ├── preprocessor.pkl        # Fitted transformer
│   └── configs.yaml            # Hyperparameters + metadata
├── train_and_save.py           # One-shot training pipeline
├── requirements.txt
├── .env.example                # Environment variable template
└── DEPLOYMENT.md               # This file
```
