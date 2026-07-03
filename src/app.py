"""
app.py
======
FastAPI deployment endpoint for the best-performing model (XGBoost).

Endpoints
---------
GET  /health          — Liveness check
POST /predict         — Single-record anomaly prediction
POST /predict/batch   — Batch prediction (up to 1000 records)

Security notes
--------------
- Input is strictly validated via Pydantic models.
- No raw SQL / shell execution.
- Model loaded once at startup (not per-request).
- X-From header required for traceability (per project instructions).
"""

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import joblib
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Startup: load model + preprocessor
# ---------------------------------------------------------------------------

MODEL_DIR = Path(__file__).parent.parent / "models"

try:
    preprocessor = joblib.load(MODEL_DIR / "preprocessor.pkl")
    model        = joblib.load(MODEL_DIR / "xgboost.pkl")
    logger.info("Model and preprocessor loaded successfully.")
except FileNotFoundError as exc:
    logger.error("Model artifacts not found: %s. Run the training pipeline first.", exc)
    preprocessor = None
    model        = None


# ---------------------------------------------------------------------------
# Pydantic input schema (41 NSL-KDD features)
# ---------------------------------------------------------------------------

class NetworkRecord(BaseModel):
    """A single NSL-KDD-format network connection record."""
    duration:                  float = Field(ge=0)
    protocol_type:             str   = Field(pattern="^(tcp|udp|icmp)$")
    service:                   str
    flag:                      str
    src_bytes:                 float = Field(ge=0)
    dst_bytes:                 float = Field(ge=0)
    land:                      int   = Field(ge=0, le=1)
    wrong_fragment:            float = Field(ge=0)
    urgent:                    float = Field(ge=0)
    hot:                       float = Field(ge=0)
    num_failed_logins:         float = Field(ge=0)
    logged_in:                 int   = Field(ge=0, le=1)
    num_compromised:           float = Field(ge=0)
    root_shell:                int   = Field(ge=0, le=1)
    su_attempted:              int   = Field(ge=0, le=1)
    num_root:                  float = Field(ge=0)
    num_file_creations:        float = Field(ge=0)
    num_shells:                float = Field(ge=0)
    num_access_files:          float = Field(ge=0)
    num_outbound_cmds:         float = Field(ge=0)
    is_host_login:             int   = Field(ge=0, le=1)
    is_guest_login:            int   = Field(ge=0, le=1)
    count:                     float = Field(ge=0)
    srv_count:                 float = Field(ge=0)
    serror_rate:               float = Field(ge=0, le=1)
    srv_serror_rate:           float = Field(ge=0, le=1)
    rerror_rate:               float = Field(ge=0, le=1)
    srv_rerror_rate:           float = Field(ge=0, le=1)
    same_srv_rate:             float = Field(ge=0, le=1)
    diff_srv_rate:             float = Field(ge=0, le=1)
    srv_diff_host_rate:        float = Field(ge=0, le=1)
    dst_host_count:            float = Field(ge=0)
    dst_host_srv_count:        float = Field(ge=0)
    dst_host_same_srv_rate:    float = Field(ge=0, le=1)
    dst_host_diff_srv_rate:    float = Field(ge=0, le=1)
    dst_host_same_src_port_rate: float = Field(ge=0, le=1)
    dst_host_srv_diff_host_rate: float = Field(ge=0, le=1)
    dst_host_serror_rate:      float = Field(ge=0, le=1)
    dst_host_srv_serror_rate:  float = Field(ge=0, le=1)
    dst_host_rerror_rate:      float = Field(ge=0, le=1)
    dst_host_srv_rerror_rate:  float = Field(ge=0, le=1)


class PredictionResponse(BaseModel):
    prediction:  int           # 0 = normal, 1 = attack
    label:       str           # "normal" | "attack"
    probability: float         # probability of attack class


class BatchRequest(BaseModel):
    records: list[NetworkRecord] = Field(min_length=1, max_length=1000)


class BatchResponse(BaseModel):
    predictions: list[PredictionResponse]
    total:       int


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Network Anomaly Detection API",
    description="Detects anomalous network traffic using XGBoost trained on NSL-KDD.",
    version="1.0.0",
)


@app.get("/health")
def health(x_from: Optional[str] = Header(default=None)):
    _require_x_from(x_from)
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "preprocessor_loaded": preprocessor is not None,
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(
    record: NetworkRecord,
    x_from: Optional[str] = Header(default=None),
):
    _require_x_from(x_from)
    _check_model_ready()

    df = _record_to_df([record])
    X  = preprocessor.transform(df)

    prob  = float(model.predict_proba(X)[0, 1])
    pred  = int(prob >= 0.5)
    return PredictionResponse(
        prediction=pred,
        label="attack" if pred == 1 else "normal",
        probability=round(prob, 4),
    )


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(
    batch: BatchRequest,
    x_from: Optional[str] = Header(default=None),
):
    _require_x_from(x_from)
    _check_model_ready()

    df    = _record_to_df(batch.records)
    X     = preprocessor.transform(df)
    probs = model.predict_proba(X)[:, 1]
    preds = (probs >= 0.5).astype(int)

    results = [
        PredictionResponse(
            prediction=int(p),
            label="attack" if p == 1 else "normal",
            probability=round(float(prob), 4),
        )
        for p, prob in zip(preds, probs)
    ]
    return BatchResponse(predictions=results, total=len(results))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_x_from(x_from: Optional[str]) -> None:
    """Enforce X-From header for request traceability."""
    if not x_from:
        raise HTTPException(status_code=400, detail="X-From header is required.")


def _check_model_ready() -> None:
    if model is None or preprocessor is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run the training pipeline first.",
        )


def _record_to_df(records: list[NetworkRecord]):
    import pandas as pd
    return pd.DataFrame([r.model_dump() for r in records])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
