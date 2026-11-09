# Loan default model experiment report

Date: 2026-11-09

## Experiment

Ran six candidates on the same stratified 80/20 split (seed 42), using a 0.50 classification threshold. Precision, recall, and ROC AUC are test-set metrics.

| Candidate | Recall | Precision | ROC AUC | MLflow run |
|---|---:|---:|---:|---|
| Logistic regression, C=0.05 | 0.862 | 0.639 | 0.927 | [run 08fd0fb6](http://127.0.0.1:5000/#/experiments/1/runs/08fd0fb618b94c4184734a7202cc5a7c) |
| Logistic regression, C=0.1 | 0.853 | 0.637 | 0.927 | [run b33a362f](http://127.0.0.1:5000/#/experiments/1/runs/b33a362fcbd24c79a6cefe196ea4ed57) |
| Logistic regression, C=1.0 | 0.853 | 0.637 | 0.927 | [run 4f5b86ab](http://127.0.0.1:5000/#/experiments/1/runs/4f5b86ab9ff145c69774bddb58bdd221) |
| Random forest, depth=4 | 0.832 | 0.694 | 0.922 | [run da14c014](http://127.0.0.1:5000/#/experiments/1/runs/da14c014eb784a069b1c343d65884829) |
| Random forest, depth=8 | 0.815 | 0.716 | 0.928 | [run 4fa30aa5](http://127.0.0.1:5000/#/experiments/1/runs/4fa30aa51d364ad997f15ec64e209591) |
| Random forest, unlimited depth | 0.806 | 0.725 | 0.925 | [run ad790bee](http://127.0.0.1:5000/#/experiments/1/runs/ad790bee8e48429da41bb6e8fefaf7a8) |

## Promotion decision

I chose the logistic-regression candidate with C=0.05 as champion because, for a loan-default screening workflow, missing a likely default is the more costly error, and it has the highest recall at 0.862 while retaining 0.639 precision and 0.927 AUC. The random-forest depth-8 candidate is the challenger: its 0.928 AUC is marginally higher and its 0.716 precision is materially better, but its recall is 0.815. The champion therefore better prioritizes identifying default risk; the challenger remains available for continued comparison. See the [champion run](http://127.0.0.1:5000/#/experiments/1/runs/08fd0fb618b94c4184734a7202cc5a7c) and [challenger run](http://127.0.0.1:5000/#/experiments/1/runs/4fa30aa51d364ad997f15ec64e209591).

## Registry

Registered both candidates under `loan-default`. Alias `champion` points to version 1 (run `08fd0fb618b94c4184734a7202cc5a7c`); its version description records the recall-based selection and all three metrics. Alias `challenger` points to version 2 (run `4fa30aa51d364ad997f15ec64e209591`); its description records its alternative-model/AUC rationale and metrics.

For production, `export_champion.py` exports the champion to `champion_model.joblib` (version 1, run `08fd0fb618b94c4184734a7202cc5a7c`). The service loads that artifact by default (`MODEL_SOURCE=artifact`) so a deploy is reproducible and does not depend on a live tracking server; `MODEL_SOURCE=registry` still loads `models:/loan-default@champion` for local lifecycle work.

## Serving and integration

All three programs were started and checked:

- MLflow tracking/registry: `http://127.0.0.1:5000` — `/health` returned HTTP 200.
- MLflow scoring server: `http://127.0.0.1:5001` — `/health` returned HTTP 200.
- FastAPI: `http://127.0.0.1:8000` — `/health` returned `{"status":"ok","model_version":"1","git_sha":"dev"}`. The SHA is `dev` locally; the deployed app reports the commit that the pipeline stamped.

For applicant `{amount_usd: 1500, term_months: 12, monthly_income_usd: 350.0, previous_loans: 1, late_payments: 0}`, MLflow `/invocations` returned probability `0.10312231230129174`; FastAPI `/api/v1/predictions` returned `0.103`. The difference is `0.000122`, due to FastAPI's three-decimal response rounding. A scoring request missing the required `late_payments` column was rejected with HTTP 400 (`INVALID_PARAMETER_VALUE`) by MLflow signature enforcement.

## Drift monitoring

`monitor.py` compared 1,000 current synthetic records with the 5,000-record training reference. The chart uses PSI <0.10 as stable, 0.10–<0.20 as a warning, and >=0.20 as an alert. `amount_usd` scored 0.384 and `late_payments` 0.569, both alerting; all other features scored below 0.012. The warning and alert thresholds are therefore set at PSI 0.10 and 0.20, respectively.

![Feature drift PSI chart with warning and alert thresholds](artifacts/drift-monitor.png)

## Rollback verification and tests

Moved `champion` to version 2, restarted FastAPI, and verified `/health` returned model version `2`. Restored the alias to version 1, restarted FastAPI, and verified `/health` returned model version `1`. The regression suite passed: `10 passed` after the release-level rollback described in the next section.

## Release engineering: CI, deployment, security, and rollback

Repository: <https://github.com/TithVichra/loan-api>  
Live app: <https://loan-api.fastapicloud.dev>  
Health: <https://loan-api.fastapicloud.dev/health>

### Pipeline and branch protection

`.github/workflows/pipeline.yml` runs `pytest` on every pull request and every push to `main`. The `deploy` job runs only for pushes to `main` when the repository variable `DEPLOY_ENABLED` is `true`. It stamps `GITHUB_SHA` into `version.json`, deploys with the FastAPI Cloud CLI, then runs `scripts/smoke.py`. The smoke check waits for the deployed SHA, requires two consecutive consistent `/health` + prediction pairs (same SHA, same model version, `risk_band=low`), and fails on a genuine bad release. Branch protection on `main` requires the `test` check, requires branches to be up to date, enforces the rule for admins, and blocks force pushes and deletions.

The production app serves the exported champion artifact (`champion_model.joblib`, version 1, run `08fd0fb618b94c4184734a7202cc5a7c`) instead of retraining at boot. `/health` returns `status`, `model_version`, and `git_sha`; the SHA is read from `GIT_SHA` or `version.json`, which the deploy job writes from `GITHUB_SHA`.

### API key and secrets

Every `/api/v1/*` route requires `X-API-Key`; `/health` stays public for the pipeline. Missing key -> `401` with `WWW-Authenticate: ApiKey`; wrong key -> `403`; correct key -> `200`. The 64-character key is generated locally, stored as the FastAPI Cloud secret `API_KEY` and the GitHub Actions secret `LOAN_API_KEY`, and is never committed. `.env` is ignored, the deploy token lives in the GitHub Actions secret `FASTAPI_CLOUD_TOKEN`, and the workflow logs mask the values as `***`.

Live checks (2026-11-09, SHA `67ed799`):

- `GET /health` -> `200 {"status":"ok","model_version":"1","git_sha":"67ed799..."}`
- `POST /api/v1/predictions` without a key -> `401`, `www-authenticate: ApiKey`
- wrong key -> `403`
- correct key -> `200 {"default_probability":0.103,"risk_band":"low","model_version":"1"}`

### TLS

SSL Labs (`https://api.ssllabs.com/api/v3/analyze?host=loan-api.fastapicloud.dev`) reports **B** for all four edge endpoints, with no warnings. The grade is limited because the Cloudflare edge still accepts TLS 1.0 and 1.1 (TLS 1.2 and 1.3 are also enabled). This is an edge/provider setting, not application code; the remediation is to raise the minimum TLS version at the edge. The app does not terminate TLS itself.

### Bad release drill

- PR #5 (`feat: simplify risk band thresholds`, commit `6c245db`) inverted the band mapping. It passed the 9 existing tests because they only asserted membership in `{low, medium, high}`.
- The merge (`edcd5af`) deployed through the pipeline (run [42641416900](https://github.com/TithVichra/loan-api/actions/runs/42641416900)).
- The post-deploy check saw the new SHA and then `POST /api/v1/predictions` returned `{"default_probability":0.103,"risk_band":"high"}`. It failed with `FAIL: expected risk_band=low, got high`; the deploy job failed and the bad version was live.
- Rollback PR #6 reverted `6c245db` (revert commit `9d335d6`) and added `test_known_low_risk_applicant_is_low`, which pins the known low-risk applicant to `risk_band=low`. It merged as `1aa4444` (run [42642104052](https://github.com/TithVichra/loan-api/actions/runs/42642104052)).
- The first rollback verification hit a rolling-update race: `/health` came from a new instance while the prediction came from an old instance. The live app was serving `risk_band=low` again by 15:13:36, and the pipeline re-run passed at 15:14:13 with `git_sha=1aa4444...` and `risk_band=low`.
- PR #7 hardened the check to require two consecutive consistent health + prediction pairs. The final pipeline run [42643177702](https://github.com/TithVichra/loan-api/actions/runs/42643177702) passed at 15:18:49 with live SHA `4185836...` and `risk_band=low`.

### Timings (UTC, 2026-11-09)

| Event | Merge / run start | Verified live | Elapsed |
|---|---:|---:|---:|
| First fully green deploy (PR #4, `67ed799`) | 14:57:43 | 14:58:57 | 74 s |
| Bad release detected (PR #5, `edcd5af`) | 15:07:22 | 15:08:34 (failure) | 72 s |
| Rollback live (PR #6, `1aa4444`) | 15:11:19 | 15:13:36 (manual); 15:14:13 (pipeline re-run) | 2 min 17 s / 2 min 54 s |
| Final hardened deploy (PR #7, `4185836`) | 15:17:32 | 15:18:49 | 77 s |

The deploy step itself took 23-27 seconds; the rest is checkout, test, and the post-deploy check.

### Evidence links

- CI green on `main` (PR #1 baseline): <https://github.com/TithVichra/loan-api/actions/runs/42636092417>
- First fully green deploy: <https://github.com/TithVichra/loan-api/actions/runs/42639791760>
- Bad release failure: <https://github.com/TithVichra/loan-api/actions/runs/42641416900>
- Rollback (green on attempt 2): <https://github.com/TithVichra/loan-api/actions/runs/42642104052>
- Final hardened deploy: <https://github.com/TithVichra/loan-api/actions/runs/42643177702>
- Pull requests: <https://github.com/TithVichra/loan-api/pulls?q=is%3Apr>

### Path to the first green deploy

PR #2 deployed `5a117b2`, but the post-deploy check was blocked by Cloudflare (`403 error code: 1010`) because it used the default `Python-urllib` signature. PR #3 made the check tolerate non-JSON startup responses; PR #4 added a normal `User-Agent` and `Accept` header. PR #4 (`67ed799`) was the first fully green deploy. PR #7 then removed the rolling-update race exposed during the rollback. The intermediate failed runs are part of the evidence, not hidden.
