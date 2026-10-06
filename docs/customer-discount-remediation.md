# Customer discount source-remediation demo

> Current execution policy: [General source remediation](general-source-execution.md).
> The historical two-demo write restriction below has been superseded for new proposals.


Current architecture and live AI result: [general AI remediation](general-ai-remediation.md).
The implementation history below predates the generalization; current proposals
use the same AI pipeline for all safely resolved failed DAGs.

## Baseline and readiness

The supplied requirements contained `[PASTE THE DAG CODE HERE]` rather than the
source itself. The exact named file already existed in `D:\Projects\airflow\dags`.
That file was inspected and copied byte-for-byte into `demo_dags` as the reset and
structural-validation baseline. Its original fixture and declarations are retained.

The live file already contains `normalized_tier = tier.lower()` and a customer
with `"tier": None`. No live DAG source was written, reset, approved or triggered
during this implementation. A read-only Airflow check confirmed the live file
matches the repository baseline, Airflow serves that source, the DAG is unpaused,
not stale, and has no import errors.

Buggy baseline SHA-256:
`32c4873b1a7b0523e93cbdb15afc33a870f2aad83472828c9163326e3d5f1ead`.

## Explicit policy

The writable set is exactly:

- `support_intelligence_code_remediation_demo` → `summarize_transactions`
- `support_intelligence_customer_discount_remediation_demo` → `calculate_customer_discounts`

The order-metrics demo and all other DAGs remain rejected. No arbitrary path or
DAG can be supplied to expand this set. Root containment, traversal rejection,
symlink/junction checks, exact file/function/change target, stale-source SHA-256,
exact revision/hash approval, backup, atomic replace, parse recognition, rollback,
run/task/version/source verification and persisted audit all reuse the existing
workflow. The original demo still uses its original policy and baseline.

The new policy preserves the whole module outside its target function, its
signature, docstring and original customer fixture. Only this policy additionally
allows `str`, `.lower()`, `.strip()`, multiplication and subtraction. The original
policy does not gain those allowances. Syntax/AST checks never execute DAG code.
Validation does not prove arbitrary edited logic semantically correct: the
engineer still reviews the exact code, diff and business behavior before approval.

## Proposal and expected results

Developer Copilot uses the same real evidence/classification pipeline and supplies
the actual DAG, task, AttributeError, exception message, logs, timeline, developer
request and current source to the configured structured LLM provider. A valid
model result is labelled `developer_llm`. Invalid/unavailable provider output may
use this demo's `controlled_demo_fallback` only when explicitly opted in for
infrastructure testing. Default failure returns no proposal. Fallback is never AI-generated.

The fallback changes only normalization in the actual current function:

```python
normalized_tier = tier.strip().lower() if isinstance(tier, str) and tier.strip() else ""
```

The fixture still contains None. Non-string/blank tiers take the existing default
no-discount branch. No mode, runtime configuration recovery switch, or hidden
corrected branch is added.

| Customer | Original | Discount | Final |
| --- | ---: | ---: | ---: |
| CUST-1001 | 500.0 | 20% | 400.0 |
| CUST-1002 | 300.0 | 10% | 270.0 |
| CUST-1003 | 250.0 | 0% | 250.0 |

The task prints `ProcessedCustomers=3` and returns three results. Verification
checks the corrected source, expected task, DAG run and Airflow version; the
engineer must also inspect the business results in the task logs.

## Reset only this demo

The existing reset command now has a `--dag-id` argument whose choices are only
the two registered demos. Its default remains the original transaction demo.
There are no arbitrary source/destination path arguments. Reset backs up existing
bytes before replacing them with the registered intentionally buggy baseline.
Do not reset during an active review/execution or the automated test suite.

For a later repeat demonstration, explicitly run:

```powershell
cd D:\Projects\airflow-support-intelligence
.venv/Scripts/python.exe -B scripts/reset_code_remediation_demo.py --confirm-reset --dag-id support_intelligence_customer_discount_remediation_demo
```

**No reset is needed for the currently verified buggy state.**

## Manual live sequence

Restart/reload the backend and refresh the frontend to load the two-demo policy.
Keep one backend process for the existing JSON stores. Use your configured LLM
provider with `GEMINI_MODEL=gemini-3.5-flash-lite` for the live AI test. Leave
**Allow labelled demo fallback** unchecked. `LLM_PROVIDER=none` produces no AI
proposal; fallback testing additionally requires that explicit checkbox.

In Airflow, open `support_intelligence_customer_discount_remediation_demo`, confirm
it is unpaused, and trigger with an empty JSON configuration `{}`. Alternatively,
use the following commands yourself (they create the initial failing run):

```powershell
$dag = 'support_intelligence_customer_discount_remediation_demo'
$airflow = 'http://localhost:8088'
# Replace credentials if your local Airflow defaults differ.
$auth = Invoke-RestMethod -Method Post -Uri "$airflow/auth/token" -ContentType 'application/json' -Body '{"username":"airflow","password":"airflow"}'
$headers = @{ Authorization = "Bearer $($auth.access_token)" }
$run = Invoke-RestMethod -Method Post -Uri "$airflow/api/v2/dags/$dag/dagRuns" -Headers $headers -ContentType 'application/json' -Body '{"logical_date":null,"conf":{}}'
$run.dag_run_id
```

1. Wait for the natural AttributeError: `'NoneType' object has no attribute 'lower'`.
2. Select this DAG in Support Intelligence and click **Analyze Live Airflow**.
   With ML insufficient and LLM unavailable, expect Application Code,
   EVIDENCE_SIGNAL_FALLBACK, human review required, and real exception/task evidence.
3. Ask Developer Copilot: "Investigate this failure and propose a source-code correction."
   Require `developer_llm` provenance; inspect root cause, evidence, reasoning and assumptions.
4. Open **Review Proposed Change**. Check the actual current source and proposed source.
5. Optionally edit normalization, e.g. use `"standard"` instead of `""` as the default
   tier. Save Reviewed Version; inspect the regenerated diff and new revision.
6. Validate, inspect the exact hash, enter your reviewer identity, and explicitly
   approve that revision. Editing again invalidates its validation and approval.
7. Only when ready, explicitly click **Execute Approved Remediation**. Observe
   backup/application, Airflow source recognition, corrected trigger with `conf={}`,
   and successful task/DAG verification. No automatic patch/retry loop is enabled.
8. Inspect the corrected run's task logs for all three final totals and
   `ProcessedCustomers=3`. Review the persisted audit and submit Engineer Feedback.

Saved source reviews are available for every safely resolved DAG with a proposal. A review selected for one DAG
is not shown as the workspace for the other selected DAG.

## Historical files changed for the original demo addition

- Added `demo_dags/support_intelligence_customer_discount_remediation_demo.py`:
  exact existing local buggy baseline, copied into the repository only.
- Updated `backend/app/source_validation.py`: finite policy registry and per-demo
  baseline/function/fixture/task validation.
- Updated `backend/app/source_patch_generator.py`: demo-specific structured prompt
  and minimal honestly labelled customer fallback.
- Updated `backend/app/developer_copilot.py`: route both supported demos through
  the existing grounded source proposal workflow with the actual DAG ID.
- Updated `backend/app/source_remediation.py` and `source_updater.py`: exact
  registered DAG/function targeting throughout create, validate and apply.
- Updated `backend/app/source_airflow.py`: registered DAG recognition and expected
  task verification for each demo.
- Updated `scripts/reset_code_remediation_demo.py`: finite CLI choices and reset
  helper; original default retained.
- Updated `frontend/src/App.jsx`: workspace/history access for both demos, scoped
  to the selected DAG. No visual redesign.
- Added `tests/test_customer_discount_remediation.py`; updated the fake Airflow
  boundary in `tests/test_source_remediation.py` and parametrized both demos in
  `tests/test_source_browser.py`.
- Updated `docs/source-remediation.md` and added this report.

## Historical verification before generalization

Focused customer/original source-remediation and classification tests: **83 passed**.
Complete backend suite: **208 passed, 4 optional browser cases skipped**.
Frontend lint and production build passed. Four existing dependency deprecation
warnings remain. The session fingerprint guard confirmed real Airflow DAG files
were unchanged during automated tests. All source-write/reset tests use temporary
DAG roots, and reset backups also remain in temporary storage.

The tests cover policy rejection, actual source/context, provenance, preserved
fixtures, exact business totals, invalid source, edits/diffs/approval invalidation,
stale source, old revisions, backup, exact bytes, rollback, empty trigger configuration,
task/source verification, no retry loop, isolated reset and original-demo regression.
Only the known deterministic function is executed in the business-result unit test;
validation never executes source or provider output.

Opt-in Chrome browser workflows: **4 passed**, covering both original runtime
scenarios and both source-demo edit/approve/execute/feedback/reload scenarios
against mocked Airflow and temporary DAG files.
The live apply/execute acceptance remains deliberately reserved for the engineer.
