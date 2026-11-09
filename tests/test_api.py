"""Run with: pytest -v (the champion artifact is committed as champion_model.joblib)."""
import pytest
from fastapi.testclient import TestClient

import main
from main import APPLICATIONS, app

GOOD = {"amount_usd": 1500, "term_months": 12, "monthly_income_usd": 350.0, "previous_loans": 1, "late_payments": 0}
LOW_RISK = {"amount_usd": 500, "term_months": 24, "monthly_income_usd": 1000.0, "previous_loans": 0, "late_payments": 0}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "API_KEY", None)
    APPLICATIONS.clear()
    with TestClient(app) as c:  # "with" runs the lifespan, so the model is loaded
        yield c


@pytest.fixture
def secured_client(monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "test-key")
    APPLICATIONS.clear()
    with TestClient(app) as c:
        yield c


def test_root_landing_page(client):
    root = client.get("/").json()
    assert root["service"] == "loan-api"
    assert root["status"] == "ok"
    assert root["docs"] == "/docs"
    assert root["health"] == "/health"
    assert root["git_sha"]


def test_health_reports_model_version_and_sha(client):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["model_version"] == "1"
    assert health["git_sha"]


def test_prediction_is_a_probability(client):
    body = client.post("/api/v1/predictions", json=GOOD).json()
    assert 0 <= body["default_probability"] <= 1
    assert body["risk_band"] in {"low", "medium", "high"}


def test_known_low_risk_applicant_is_low(client):
    body = client.post("/api/v1/predictions", json=GOOD).json()
    assert body["risk_band"] == "low"


def test_amount_above_limit_is_rejected(client):
    assert client.post("/api/v1/predictions", json={**GOOD, "amount_usd": 9000}).status_code == 422


def test_create_and_read_application(client):
    created = client.post("/api/v1/applications", json={**GOOD, "borrower_id": 1042})
    assert created.status_code == 201
    app_id = created.json()["id"]
    assert client.get(f"/api/v1/applications/{app_id}").json()["borrower_id"] == 1042


def test_missing_application_is_404(client):
    assert client.get("/api/v1/applications/99999").status_code == 404


def test_health_stays_public_when_auth_is_enabled(secured_client):
    assert secured_client.get("/health").status_code == 200


def test_api_key_missing_returns_401(secured_client):
    response = secured_client.post("/api/v1/predictions", json=GOOD)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"


def test_api_key_invalid_returns_403(secured_client):
    response = secured_client.post("/api/v1/predictions", json=GOOD, headers={"X-API-Key": "wrong"})
    assert response.status_code == 403


def test_api_key_valid_returns_200(secured_client):
    response = secured_client.post("/api/v1/predictions", json=GOOD, headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert 0 <= response.json()["default_probability"] <= 1
