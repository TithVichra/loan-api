"""Loan Application Service: stores loan applications and scores their default risk."""
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException

from schemas import Application, ApplicationCreate, LoanFeatures, Prediction

ml = {}            # filled at start-up: {"model": ..., "version": ..., "features": [...], "sha": ...}
APPLICATIONS = {}  # in-memory store; resets when the server restarts

MODEL_SOURCE = os.getenv("MODEL_SOURCE", "artifact")  # "artifact" (default) or "registry"
MODEL_ARTIFACT = os.getenv("MODEL_ARTIFACT", "champion_model.joblib")
MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "loan-default")
MODEL_ALIAS = os.getenv("MLFLOW_MODEL_ALIAS", "champion")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "")
VERSION_FILE = Path(os.getenv("VERSION_FILE", "version.json"))
FEATURES = ["amount_usd", "term_months", "monthly_income_usd", "previous_loans", "late_payments"]


def _deployed_sha() -> str:
    sha = os.getenv("GIT_SHA")
    if sha:
        return sha
    try:
        return str(json.loads(VERSION_FILE.read_text(encoding="utf-8"))["sha"])
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"


def _load_artifact():
    bundle = joblib.load(MODEL_ARTIFACT)
    if isinstance(bundle, dict):
        return bundle["model"], str(bundle.get("version", "unknown"))
    return bundle, "unknown"


def _load_registry():
    import mlflow

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.MlflowClient()
    version = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{MODEL_ALIAS}")
    return model, str(version.version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if MODEL_SOURCE == "registry":
        model, version = _load_registry()
    else:
        model, version = _load_artifact()
    ml.update({"model": model, "version": version, "features": FEATURES, "sha": _deployed_sha()})
    yield
    ml.clear()


app = FastAPI(title="Loan Application Service", version="1.1.0", lifespan=lifespan)


def _default_probability(model, features: LoanFeatures) -> float:
    X = pd.DataFrame([features.model_dump()])[ml["features"]]
    if hasattr(model, "predict_proba"):
        return float(model.predict_proba(X)[0, 1])
    return float(model.predict(X)[0])


def score(features: LoanFeatures) -> Prediction:
    probability = _default_probability(ml["model"], features)
    band = "low" if probability < 0.2 else "medium" if probability < 0.5 else "high"
    return Prediction(default_probability=round(probability, 3), risk_band=band, model_version=ml["version"])


@app.get("/health")
def health():
    return {"status": "ok", "model_version": ml.get("version"), "git_sha": ml.get("sha", "unknown")}


@app.post("/api/v1/predictions", response_model=Prediction)
def predict(features: LoanFeatures):
    return score(features)


@app.post("/api/v1/applications", response_model=Application, status_code=201)
def create_application(body: ApplicationCreate):
    new = Application(id=7781 + len(APPLICATIONS), status="pending",
                      prediction=score(body), **body.model_dump())
    APPLICATIONS[new.id] = new
    return new


@app.get("/api/v1/applications", response_model=list[Application])
def list_applications():
    return list(APPLICATIONS.values())


@app.get("/api/v1/applications/{application_id}", response_model=Application)
def get_application(application_id: int):
    if application_id not in APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return APPLICATIONS[application_id]
