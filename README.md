# Loan Application Service

FastAPI service that stores loan applications and scores their default risk with the promoted champion model.

- Repository: <https://github.com/TithVichra/loan-api>
- Live app: <https://loan-api.fastapicloud.dev>
- Health: <https://loan-api.fastapicloud.dev/health>

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | public | Service landing page with links and deployed commit |
| `GET` | `/health` | public | Status, model version, deployed commit |
| `POST` | `/api/v1/predictions` | `X-API-Key` | Score one applicant |
| `POST` | `/api/v1/applications` | `X-API-Key` | Create and score an application |
| `GET` | `/api/v1/applications` | `X-API-Key` | List applications |
| `GET` | `/api/v1/applications/{id}` | `X-API-Key` | Read one application |

The application store is in memory and resets when the process restarts.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Optional: if API_KEY is unset, authentication is disabled.
$env:API_KEY = "local-dev-key"
$env:MODEL_SOURCE = "artifact"
uvicorn main:app --reload
```

The service loads `champion_model.joblib` by default. To load `models:/loan-default@champion` from MLflow instead, set `MODEL_SOURCE=registry` and `MLFLOW_TRACKING_URI`.

## Test

```powershell
pytest -q
```

The suite covers the health contract, validation, the in-memory application flow, the 401/403/200 API-key paths, and the known low-risk band.

## Model

`champion_model.joblib` is the exported champion: logistic regression with `C=0.05`, version 1, MLflow run `08fd0fb618b94c4184734a7202cc5a7c`, test metrics recall 0.862, precision 0.639, ROC AUC 0.927. Re-export it with:

```powershell
python export_champion.py
```

See `REPORT.md` for the six-candidate comparison, promotion decision, drift monitoring, and release drill.

## Deployment

Every pull request runs the tests. A push to `main` deploys only through `.github/workflows/pipeline.yml` when the repository variable `DEPLOY_ENABLED` is `true`; the job stamps the commit into `version.json`, deploys with the FastAPI Cloud CLI, and verifies the live SHA plus a known low-risk prediction.

Required GitHub Actions secrets:

- `FASTAPI_CLOUD_TOKEN` — app deploy token
- `FASTAPI_CLOUD_APP_ID` — FastAPI Cloud app id
- `LOAN_API_KEY` — the same key configured as the app's `API_KEY` secret

Required repository variables:

- `DEPLOY_ENABLED` — `true`
- `LIVE_BASE_URL` — `https://loan-api.fastapicloud.dev`

Branch protection on `main` requires the `test` check and blocks force pushes and deletions. No secret is committed; `.env` is ignored.

## Security notes

- `/api/v1/*` returns `401` (`WWW-Authenticate: ApiKey`) when the key is missing and `403` when it is wrong.
- The production image runs as `appuser` and installs only runtime dependencies; `mlflow` is development-only.
- SSL Labs grades the live edge **B** because Cloudflare still accepts TLS 1.0 and 1.1. The app does not terminate TLS; raising the edge minimum to TLS 1.2 is the remediation.
- The container image still has 47 HIGH Trivy findings in the Debian base (0 CRITICAL). See `CHECKLIST.md`; the release gate remains open for the container image.
