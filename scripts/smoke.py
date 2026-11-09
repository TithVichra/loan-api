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


def _decode(raw: bytes) -> dict:
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        return {"raw": raw.decode(errors="replace")[:200]}


def request(method: str, path: str, body: dict | None = None, key: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "loan-api-smoke/1.0",
    }
    if key is not None:
        headers["X-API-Key"] = key
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, _decode(response.read())
    except urllib.error.HTTPError as error:
        return error.code, _decode(error.read())
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, {"error": str(error)}


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

    stable = 0
    deadline = time.monotonic() + 120
    prediction = {}
    while time.monotonic() < deadline:
        status_h, health_now = request("GET", "/health")
        status_p, prediction = request("POST", "/api/v1/predictions", GOOD, key=API_KEY)
        print(f"{now()} GET /health -> {status_h} {health_now}", flush=True)
        print(f"{now()} POST /api/v1/predictions -> {status_p} {prediction}", flush=True)
        consistent = (
            status_h == 200
            and health_now.get("git_sha") == EXPECTED_SHA
            and status_p == 200
            and prediction.get("risk_band") == "low"
            and prediction.get("model_version") == health_now.get("model_version")
        )
        stable = stable + 1 if consistent else 0
        if stable >= 2:
            health = health_now
            break
        time.sleep(3)
    else:
        print("FAIL: the new version never served two consistent low-risk predictions", flush=True)
        return 1

    print(json.dumps({"verified_sha": EXPECTED_SHA, "health": health, "prediction": prediction}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
