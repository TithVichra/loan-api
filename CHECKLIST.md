# Production checklist: loan-api 1.0.0

Review and verification date: 2026-11-09
Commands below were run from the `loan-api` project directory.

## 1. Slim base image

- [x] Use a slim Python base image. `Dockerfile.prod` uses `python:3.12-slim` in both stages.
- [x] Production image build passed.

## 2. Multi-stage build

- [x] Install dependencies and train the model in the `builder` stage.
- [x] Copy only the virtual environment, trained model, and API source to the final stage.
- [x] `docker build -f Dockerfile.prod -t loan-api:1.0.0 .` — passed.

## 3. Dev dependencies separated

- [x] Keep test dependencies in `requirements-dev.txt` (`pytest`).
- [x] Install only `requirements.txt` in the production image.

## 4. Non-root user

- [x] Configure the final image to run as `appuser`.
- [x] `docker image inspect --format 'User={{.Config.User}} Healthcheck={{json .Config.Healthcheck.Test}}' loan-api:1.0.0` — reported `User=appuser`.

## 5. Pinned versions

- [x] Pin Python package versions in `requirements.txt` and `requirements-dev.txt`.
- [ ] Pin both `FROM` references in `Dockerfile.prod` to immutable image digests. `python:3.12-slim` is a mutable tag, even though the build resolved it to a digest.

## 6. HEALTHCHECK

- [x] Configure the Docker `HEALTHCHECK` to call the API's `/health` endpoint.
- [x] Start the production image and wait for Docker health status — `healthy`; `/health` returned `{"status":"ok","model_version":"1.0.0"}`.

## 7. Vulnerability scan (Trivy 0.69.3, HIGH and CRITICAL)

- [x] Build the image and scan it with Trivy 0.69.3.
- [ ] Resolve or formally accept the HIGH findings and rerun the scan with a failing threshold (`--exit-code 1`). Release gate: **FAIL** until findings are addressed.

Scan findings for `loan-api:1.0.0` (Debian 13.7): **47 HIGH, 0 CRITICAL**. Examples reported include util-linux CVEs `CVE-2026-76642`, `CVE-2026-78408`, `CVE-2026-78409`, and `CVE-2026-78410`; `CVE-2026-54369` in `libacl1`; `CVE-2025-69720` in `ncurses-base`; and `CVE-2026-9538` in `perl-base` (reported as `fix_deferred`). Several findings apply to multiple installed packages. The scan command returned exit code 0 because it did not set `--exit-code`; this does not mean the findings are clear.

### Commands run and results

Run these from `loan-api`:

```powershell
docker build -f Dockerfile.prod -t loan-api:1.0.0 .
# Passed; image built as loan-api:1.0.0.

docker image inspect --format 'User={{.Config.User}} Healthcheck={{json .Config.Healthcheck.Test}}' loan-api:1.0.0
# User=appuser; health-check command targets http://127.0.0.1:8000/health.

docker run --rm --detach --name loan-api-healthcheck -p 127.0.0.1:18001:8000 loan-api:1.0.0
# Started; Docker health status became healthy. Container was stopped after verification.

docker run --rm aquasec/trivy:0.69.3 --version
# Version: 0.69.3.

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.69.3 image --scanners vuln --severity HIGH,CRITICAL --format table loan-api:1.0.0
# Completed; Total: 47 (HIGH: 47, CRITICAL: 0). Exit code 0 is not a clean-scan result.
```
