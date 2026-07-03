"""
test_api.py
===========
Tests for the FastAPI endpoints in src/app.py.
Uses FastAPI's TestClient — no running server required.
"""

import pytest
from fastapi.testclient import TestClient

from src.app import app

client = TestClient(app, raise_server_exceptions=True)

HEADERS = {"X-From": "pytest"}


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self):
        resp = client.get("/health", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["model_loaded"] is True
        assert body["preprocessor_loaded"] is True

    def test_health_missing_x_from(self):
        resp = client.get("/health")
        assert resp.status_code == 400
        assert "X-From" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /predict — happy paths
# ---------------------------------------------------------------------------

class TestPredict:
    def test_normal_traffic(self, normal_record):
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["prediction"] == 0
        assert body["label"] == "normal"
        assert 0.0 <= body["probability"] <= 1.0

    def test_attack_traffic(self, attack_record):
        resp = client.post("/predict", json=attack_record, headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["prediction"] == 1
        assert body["label"] == "attack"
        assert body["probability"] > 0.5

    def test_response_schema(self, normal_record):
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        body = resp.json()
        assert set(body.keys()) == {"prediction", "label", "probability"}
        assert isinstance(body["prediction"], int)
        assert isinstance(body["label"], str)
        assert isinstance(body["probability"], float)

    def test_probability_between_0_and_1(self, normal_record):
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        prob = resp.json()["probability"]
        assert 0.0 <= prob <= 1.0

    def test_label_matches_prediction(self, normal_record):
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        body = resp.json()
        expected_label = "attack" if body["prediction"] == 1 else "normal"
        assert body["label"] == expected_label


# ---------------------------------------------------------------------------
# /predict — validation / error cases
# ---------------------------------------------------------------------------

class TestPredictValidation:
    def test_missing_x_from(self, normal_record):
        resp = client.post("/predict", json=normal_record)
        assert resp.status_code == 400
        assert "X-From" in resp.json()["detail"]

    def test_invalid_protocol_type(self, normal_record):
        normal_record["protocol_type"] = "ftp"  # not in tcp|udp|icmp
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        assert resp.status_code == 422

    def test_negative_duration(self, normal_record):
        normal_record["duration"] = -1
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        assert resp.status_code == 422

    def test_rate_above_1(self, normal_record):
        normal_record["serror_rate"] = 1.5  # must be <= 1
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        assert resp.status_code == 422

    def test_binary_field_out_of_range(self, normal_record):
        normal_record["logged_in"] = 2  # must be 0 or 1
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        assert resp.status_code == 422

    def test_missing_required_field(self, normal_record):
        del normal_record["flag"]
        resp = client.post("/predict", json=normal_record, headers=HEADERS)
        assert resp.status_code == 422

    def test_empty_body(self):
        resp = client.post("/predict", json={}, headers=HEADERS)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /predict/batch
# ---------------------------------------------------------------------------

class TestPredictBatch:
    def test_batch_mixed(self, normal_record, attack_record):
        resp = client.post(
            "/predict/batch",
            json={"records": [normal_record, attack_record]},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["predictions"]) == 2
        assert body["predictions"][0]["label"] == "normal"
        assert body["predictions"][1]["label"] == "attack"

    def test_batch_single_record(self, normal_record):
        resp = client.post(
            "/predict/batch",
            json={"records": [normal_record]},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_batch_total_matches_records(self, normal_record, attack_record):
        resp = client.post(
            "/predict/batch",
            json={"records": [normal_record, attack_record, normal_record]},
            headers=HEADERS,
        )
        body = resp.json()
        assert body["total"] == len(body["predictions"]) == 3

    def test_batch_exceeds_limit(self, normal_record):
        resp = client.post(
            "/predict/batch",
            json={"records": [normal_record] * 1001},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_batch_missing_x_from(self, normal_record):
        resp = client.post("/predict/batch", json={"records": [normal_record]})
        assert resp.status_code == 400

    def test_batch_empty_records(self):
        resp = client.post(
            "/predict/batch",
            json={"records": []},
            headers=HEADERS,
        )
        # Empty batch is rejected — min_length=1 constraint
        assert resp.status_code == 422
