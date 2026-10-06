# Application Code classification fix

## Scope and inspected state

Resumed the interrupted changes without restarting implementation. The classification
code, tests, runbook and UI confidence explanation were already present and coherent.
Existing uncommitted source-remediation work and action history were preserved.
No source-write policy expansion, ML retraining or UI redesign was performed.

The classification fix touches these nine files (in addition to this report):

| File | Change |
| --- | --- |
| `backend/app/evidence_signals.py` | Runtime application exceptions, conservative ValueError rules, supporting evidence and explicit priority |
| `backend/app/llm_analyzer.py` | Application Code added to allowed response taxonomy and prompt |
| `backend/app/runbook.py` | Application Code runbook mapping |
| `backend/app/recommendation.py` | Task/source/input-specific L1 investigation guidance |
| `backend/app/developer_copilot.py` | Category-specific fix/tests and safe read-only source retrieval for unsupported application DAGs |
| `backend/app/main.py` | Source-investigation recommendation without a runtime trigger; preserve category guidance when LLM checks are absent or unrelated |
| `frontend/src/App.jsx` | Explain deterministic confidence as rule strength, not causal probability |
| `runbooks/application_code.md` | Runtime exception investigation and reviewed source-remediation procedure |
| `tests/test_application_code.py` | 33 focused taxonomy, precedence, fallback, API, Copilot and policy cases |

## Classification behavior

Existing classes remain intact. Application Code requires a structured exception
type, a failed task ID, and evidence of failure (failed DAG state or failed task
count). A PythonOperator name or a free-text exception mention alone is insufficient.
Recognized exceptions include ZeroDivisionError, TypeError, KeyError,
AttributeError, IndexError, NameError and UnboundLocalError.

ValueError remains Configuration when configuration evidence is present, including
missing service endpoints and invalid timeout configuration. Explicit conversion,
unpacking or mathematical data errors can support Application Code. An ambiguous
ValueError such as “invalid value” stays Unknown.

Deterministic priority is direct incident-specific DAG import evidence first,
then the existing Kubernetes, parsing, configuration, scheduler and resource rules,
then Application Code, finally Unknown. Existing relative domain-rule ordering
is preserved; application exceptions cannot override those domain rules. Global
import-error counts do not establish an import failure in the selected DAG.
Bare “parsing” text is no longer treated as proof of DAG parsing, because tasks
may parse ordinary input data. Structured container/OOM evidence retains the
existing Kubernetes classification; ordinary OOM/resource messages use Resource.

The hybrid analyzer itself is unchanged. When ML cannot classify and the LLM is
unavailable or Unknown, its existing EVIDENCE_SIGNAL_FALLBACK selects the new
signal, retains human review and preserves ML/LLM attribution. Confidence 0.90
uses the existing deterministic convention and is not a calibrated causal probability.

Application Code does not recommend trigger_dag or mode=recovery. It recommends
source investigation; actual remediation still requires safely resolved source,
an explicitly supported DAG, a valid proposal, validation and exact-version approval.
The order-metrics DAG remains outside the write allowlist. Copilot can retrieve
its source read-only but does not fabricate an available patch or permit application.

## Verification on 2026-10-04

- Focused classification and existing hybrid tests: **36 passed**, four dependency warnings.
- Complete backend suite: **189 passed, 3 skipped**, four dependency warnings.
- The skipped cases are opt-in browser tests, not backend failures; they were not
  rerun in this classification continuation.
- Frontend ESLint: passed. Vite production build: passed.
- `git diff --check`: passed (Git emitted line-ending notices only).
- The test session's read-only fingerprint guard confirmed real local Python DAG
  files remained unchanged. Test writes used temporary source roots/stores.

Commands used from the repository root:

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_application_code.py tests/test_hybrid_analyzer.py -q -p no:cacheprovider --basetemp=.test-runs/application-resume-focused --tb=short
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider --basetemp=.test-runs/application-resume-full --tb=short
cd frontend
npm.cmd run lint
npm.cmd run build
```

## Real Airflow acceptance

The current FastAPI application was called through TestClient against the real
local Airflow adapter, not mocked Airflow data. It re-analyzed existing run
`manual__2026-10-04T06:54:26.667138+00:00` for
`support_intelligence_order_metrics_demo`.

Observed result:

```text
Final class: Application Code
Decision mode: EVIDENCE_SIGNAL_FALLBACK
Human review: true
ML status: insufficient_features
LLM status: not_configured
Runtime exception: ZeroDivisionError
Exception message: float division by zero
Failed task: calculate_order_metrics
Failed task operator: PythonOperator
Runbook: application_code.md (success)
```

The check explicitly set LLM_PROVIDER=none in its own process to prove the
deterministic path; it did not change `.env` or the running server's configuration.
Copilot returned Application Code guidance and retrieved the actual source read-only.
Source application was still rejected by policy. Before/after hashes of all local
Python DAG files matched, and the DAG run IDs were unchanged: no run was triggered.
The detailed local result is `.test-runs/application-code-live-result.json`.

## Re-analyze in the UI or API

Restart the existing backend if it is not running with reload. To reproduce the
LLM-independent acceptance result, set LLM_PROVIDER=none in that terminal before
starting it (this does not edit your `.env`):

```powershell
cd D:\Projects\airflow-support-intelligence
$env:LLM_PROVIDER = 'none'
.venv/Scripts/python.exe -B -m uvicorn backend.app.main:app --reload --env-file .env
```

Refresh the existing frontend, select `support_intelligence_order_metrics_demo`,
and click **Analyze Live Airflow**. Check the classification, supporting evidence,
L1 checks and runbook. Ask Developer Copilot to investigate the failed input
condition. Do not trigger/reset/modify the DAG for this test.

Alternatively, in another PowerShell terminal:

```powershell
$analysis = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/analyze-airflow?dag_id=support_intelligence_order_metrics_demo'
$analysis.incident
$analysis.evidence_signals.supporting_evidence
$analysis.guidance.runbook
$analysis.guidance.l1_checks
```

This endpoint analyzes the latest run for the selected DAG; it does not accept a
historical run ID. The verified failed run was the latest at acceptance time.
Do not create a newer run if you want to reproduce that same incident.
