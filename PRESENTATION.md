# Five-minute presentation outline

Repository: <https://github.com/TithVichra/loan-api>  
Live app: <https://loan-api.fastapicloud.dev>

## Slide 1 — Title (15 s)

**Loan Application Service: from notebook to a verified release**

- Repo: `github.com/TithVichra/loan-api`
- Live: `loan-api.fastapicloud.dev`
- One line: a FastAPI loan scorer with a promoted champion, a gated pipeline, and a rehearsed rollback.

## Slide 2 — What the service does (30 s)

- Scores an applicant with five features: amount, term, monthly income, previous loans, late payments.
- Returns a default probability, a risk band, and the model version.
- Stores applications in memory (a deliberate starter limitation).
- `/health` reports the model version and the deployed commit.

## Slide 3 — Model lifecycle (45 s)

- Six candidates on the same stratified 80/20 split, seed 42.
- Champion: logistic regression `C=0.05` — recall 0.862, precision 0.639, ROC AUC 0.927.
- Why: missing a likely default costs more than a false alarm; recall wins.
- Challenger: random forest depth 8 — AUC 0.928, precision 0.716, recall 0.815.
- Production serves the exported `champion_model.joblib` (version 1, run `08fd0fb6...`), not a model retrained at boot.
- Drift: PSI alerts on `amount_usd` (0.384) and `late_payments` (0.569); thresholds 0.10 / 0.20.

## Slide 4 — Pipeline and branch protection (45 s)

- Every PR: `pytest` (10 tests).
- Push to `main`: test -> deploy with the FastAPI Cloud CLI -> stamp `GITHUB_SHA` -> smoke check.
- Smoke check: wait for the deployed SHA, then require two consecutive consistent `/health` + prediction pairs.
- `main` requires the `test` check, requires up-to-date branches, enforces the rule for admins, and blocks force pushes/deletions.
- Live app reports `git_sha`; you can prove which commit is serving.

## Slide 5 — Security (45 s)

- `X-API-Key` on every `/api/v1/*` route; `/health` stays public.
- Missing key -> `401` with `WWW-Authenticate: ApiKey`; wrong key -> `403`; correct key -> `200`.
- Key and deploy token live in FastAPI Cloud / GitHub Actions secrets; `.env` is ignored; logs show `***`.
- Image runs as `appuser`, installs only runtime dependencies, and has no API key baked in.
- TLS finding: SSL Labs **B** because the Cloudflare edge accepts TLS 1.0/1.1; remediation is an edge setting, not app code.
- Container image still has 47 HIGH Trivy findings (0 CRITICAL); the image release gate is open.

## Slide 6 — Bad release drill (60 s)

- PR #5 inverted the risk bands. The 9 existing tests passed because they only checked membership.
- Merge `edcd5af` deployed. The smoke check got `0.103` -> `high` and failed: `expected risk_band=low, got high`.
- The bad version was live; the pipeline caught it in about 72 seconds.
- Rollback PR #6 reverted the change and added `test_known_low_risk_applicant_is_low`.
- Merge `1aa4444` restored `risk_band=low`; the live app was good again within about two minutes.
- The first rollback check hit a rolling-update race; PR #7 now requires two consistent pairs. Final green run at `4185836...`.

## Slide 7 — Evidence (30 s)

| Event | Result |
|---|---|
| First fully green deploy | 74 s merge -> verified live |
| Bad release detected | 72 s, deploy job failed |
| Rollback live | ~2 min; pipeline green after re-run |
| Final hardened deploy | 77 s, green |
| API key | 401 / 403 / 200 verified live |
| TLS | SSL Labs B (TLS 1.0/1.1 at edge) |

Links: [first green deploy](https://github.com/TithVichra/loan-api/actions/runs/42639791760), [bad release](https://github.com/TithVichra/loan-api/actions/runs/42641416900), [rollback](https://github.com/TithVichra/loan-api/actions/runs/42642104052), [final](https://github.com/TithVichra/loan-api/actions/runs/42643177702).

## Slide 8 — What I would do next (30 s)

- Raise the edge minimum to TLS 1.2 and re-run SSL Labs for an A.
- Patch or formally accept the 47 HIGH base-image findings; add Trivy with `--exit-code 1` to CI.
- Replace the in-memory store with PostgreSQL and a migration.
- Add a staging environment so the smoke check runs before production, not after.
- Add authenticated load tests and a paging alert on the smoke job.

## Closing line

The model is reproducible, the release path is gated, and a bad release was caught and reversed with evidence.
