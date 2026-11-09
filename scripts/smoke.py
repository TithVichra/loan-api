"""Post-deploy verification: wait for the deployed SHA, then exercise the API."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE_URL = os.environ["BASE_URL"].rstrip("/")
EXPECTED_SHA = os.environ["EXPECTED_SHA"]
API_KEY = os.environ.get("LOAN_API_KEY", "")
GOOD = {
    "amount_usd": 1500,
    "term_months": 12,
    "monthly_income_usd": 350.0,
    "previous_loans": 1,
    "late_payments": 0,
}


def request(method: str, path: str, body: dict | None = None, key: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if key is not None:
        headers["X-API-Key"] = key
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    deadline = time.monotonic() + 300
    health = {}
    while time.monotonic() < deadline:
        status, health = request("GET", "/health")
        print(f"{now()} GET /health -> {status} {health}", flush=True)
        if status == 200 and health.get("status") == "ok" and health.get("git_sha") == EXPECTED_SHA:
            break
        time.sleep(5)
    else:
        print(f"FAIL: live SHA did not become {EXPECTED_SHA}", flush=True)
        return 1

    status, prediction = request("POST", "/api/v1/predictions", GOOD, key=API_KEY)
    print(f"{now()} POST /api/v1/predictions -> {status} {prediction}", flush=True)
    if status != 200:
        print("FAIL: prediction request was not accepted", flush=True)
        return 1
    if prediction.get("risk_band") != "low":
        print(f"FAIL: expected risk_band=low, got {prediction.get('risk_band')}", flush=True)
        return 1
    if prediction.get("model_version") != health.get("model_version"):
        print("FAIL: model version differs between /health and prediction", flush=True)
        return 1

    print(json.dumps({"verified_sha": EXPECTED_SHA, "health": health, "prediction": prediction}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
