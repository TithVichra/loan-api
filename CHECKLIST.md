# Production checklist: loan-api 1.1.0

Review and verification date: 2026-11-09
Commands below were run from the `loan-api` project directory.

## 1. Slim base image

- [x] Use a slim Python base image. `Dockerfile.prod` uses `python:3.12-slim` in both stages.
- [x] Production image build passed.

## 2. Multi-stage build

- [x] Install runtime dependencies in the `builder` stage.
- [x] Copy only the virtual environment, the exported champion artifact, and the API source to the final stage.
- [x] The image does not train a model at build or start-up; it serves `champion_model.joblib`.
- [x] `docker build -f Dockerfile.prod -t loan-api:1.1.0 --build-arg GIT_SHA=local-test .` — passed.

## 3. Dev dependencies separated

- [x] Keep test and MLflow lifecycle dependencies in `requirements-dev.txt`.
- [x] Install only `requirements.txt` in the production image (no `mlflow`).

## 4. Non-root user

- [x] Configure the final image to run as `appuser`.
- [x] `docker inspect --format 'User={{.Config.User}} Health={{.State.Health.Status}}' loan-api-health` — reported `User=appuser Health=healthy`.

## 5. Pinned versions

- [x] Pin Python package versions in `requirements.txt` and `requirements-dev.txt`.
- [x] Pin both `FROM` references in `Dockerfile.prod` to the immutable digest `python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`.

## 6. HEALTHCHECK

- [x] Configure the Docker `HEALTHCHECK` to call the API's `/health` endpoint.
- [x] Start the production image and wait for Docker health status — `healthy`; `/health` returned `{"status":"ok","model_version":"1","git_sha":"local-test"}`.
- [x] The cloud app returns `{"status":"ok","model_version":"1","git_sha":"<deployed commit>"}`.

## 7. Vulnerability scan (Trivy 0.69.3, HIGH and CRITICAL)

- [x] Build the image and scan it with Trivy 0.69.3.
- [ ] Resolve or formally accept the HIGH findings and rerun the scan with a failing threshold (`--exit-code 1`). Release gate: **FAIL** until findings are addressed.

Scan findings for `loan-api:1.1.0` (Debian 13.7): **47 HIGH, 0 CRITICAL** — the same count as the 1.0.0 image. Examples include util-linux CVEs `CVE-2026-76642`, `CVE-2026-78408`, `CVE-2026-78409`, and `CVE-2026-78410`; `CVE-2026-54369` in `libacl1`; `CVE-2025-69720` in `ncurses-base`; and `CVE-2026-9538` in `perl-base` (`fix_deferred`). The scan command did not set `--exit-code`; this is not a clean result. The FastAPI Cloud runtime image is built and patched by the provider and was not scanned by this command.

## 8. Release pipeline

- [x] Every pull request runs `pytest` (10 tests) in `.github/workflows/pipeline.yml`.
- [x] `main` requires the `test` check, requires branches to be up to date, enforces the rule for admins, and blocks force pushes/deletions.
- [x] Pushes to `main` deploy only through the pipeline (FastAPI Cloud CLI) and then run `scripts/smoke.py`.
- [x] The smoke check verifies the deployed `git_sha`, the model version, the API key, and a known low-risk prediction.
- [x] The app rejects a missing key with `401` (`WWW-Authenticate: ApiKey`) and a wrong key with `403`.
- [x] No secret is committed: `API_KEY` and `FASTAPI_CLOUD_TOKEN` live in FastAPI Cloud / GitHub Actions secrets; `.env` is ignored.

### Commands run and results

Run these from `loan-api`:

```powershell
docker build -f Dockerfile.prod -t loan-api:1.1.0 --build-arg GIT_SHA=local-test .
# Passed; image built as loan-api:1.1.0.

docker inspect --format 'User={{.Config.User}} Health={{.State.Health.Status}}' loan-api-health
# User=appuser Health=healthy.

docker run --rm aquasec/trivy:0.69.3 --version
# Version: 0.69.3.

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.69.3 image --scanners vuln --severity HIGH,CRITICAL --format table loan-api:1.1.0
# Completed; Total: 47 (HIGH: 47, CRITICAL: 0). Exit code 0 is not a clean-scan result.
```
