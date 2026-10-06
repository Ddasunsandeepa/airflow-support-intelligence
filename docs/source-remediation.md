# Reviewed source remediation

> Current execution policy: [General source remediation](general-source-execution.md).
> The historical two-demo write restriction below has been superseded for new proposals.


The existing architecture remains FastAPI → AirflowAdapter evidence/timeline →
ML/SHAP and deterministic evidence signals → hybrid analysis → Developer Copilot.
The existing runtime action policy, approval, executor and verification remain
separate. The new workflow consumes the same observed incident evidence and uses
the existing LLM provider transport, source resolver, function replacement helper,
source ChangeProposal/diff builder, Airflow trigger executor, verification engine,
and EngineerFeedback component/store.

## Scope and safety

The source updater has an explicit finite registry containing
`support_intelligence_code_remediation_demo.py` and
`support_intelligence_customer_discount_remediation_demo.py`. The first demo's
real bug sums `[120.0, None, 80.0]`. No runtime recovery flag exists.
The correct task totals 200.0 after filtering invalid amounts. Existing DAGs and
operational recovery have not been replaced.

The second demo handles a missing customer tier before calling string methods.
See [customer-discount setup and manual test](customer-discount-remediation.md).
It has its own baseline, function/task mapping and AST additions; these do not
expand the first demo's AST rules or authorize any other DAG.

## General AI investigation (2026-10-05)

Proposal eligibility is independent of write eligibility. Any failed DAG whose
source resolves safely under the configured root can receive an AI investigation,
an editable proposal, an authoritative diff and validation. The existing resolver
uses `<dag_id>.py`; this is not a general mapping for nested files or multiple DAGs
per module. A proposal replaces one existing top-level function and preserves the
rest of the module. Classification is supporting context, never a patch selector.

The strict `DeveloperRemediationResponse` contains status, diagnosis, root_cause,
reasoning, evidence_used, target_function, proposed_function, change_summary,
tests_to_run, risks and assumptions. Actual source, task/run metadata, logs,
timeline, ML and evidence/hybrid results accompany the developer's request.
Model output is untrusted and is composed in memory, compiled and AST-checked.
General review validation never executes the proposed Python. Execution-approved
demos additionally retain their conservative baseline/fixture/call restrictions.

The old configuration/supervisor/Kubernetes hardcoded patches were removed.
Normal provider failures return `no_proposal` with visible provider diagnostics.
Only the two registered demos can use the isolated fallback, and only with explicit
`allow_demo_fallback=true`; its provenance is `controlled_demo_fallback`.
A successful provider proposal is `developer_llm`. Legacy `controlled_fallback`
records remain readable for audit compatibility, but new proposals never use that
label. An explicit model `no_proposal` decision does not activate fallback.

See [general AI continuation and live evidence](general-ai-remediation.md) for the
current provider diagnosis, verification results and manual acceptance steps.

The editor preserves the original generated source and all saved revisions.
Save recalculates the authoritative diff and performs syntax checking; invalid
drafts can be saved but cannot be approved. Every changed save increments the
revision and clears validation and approval. Reset creates another revision of
the original proposal. Unsaved UI edits disable approval/execution immediately.
Requests include the expected revision/hash to reject stale browser tabs.

Full validation checks syntax, baseline DAG/task/import structure, constrained
target path, intended file, and unchanged original SHA-256. Approval requires a
named L2/ADMIN reviewer and matches the exact revision/hash. Explicit execution
checks those values again and checks the trigger policy. Local PoC identities
and roles are self-declared, consistent with the existing unauthenticated demo;
this is not production authorization. Keep the backend on trusted localhost.

The dedicated updater resolves its fixed target rather than accepting client
paths. It rejects symlinks/junctions, traversal and other DAG names. It rechecks
the base hash, creates a unique backup of real file bytes, persists the backup
reference, then atomically replaces the file using a same-directory temporary
file. Exact approved UTF-8 bytes are written, including the reviewed newlines.
No source write happens on chat, review, edit, reset-proposal or validation.

After application, Airflow 3's `/dagSources/{dag_id}` content must match the
reviewed source (CRLF/LF normalized), `/dags/{dag_id}/details` must report a newer
parse time, correct relative filename, no import errors, not stale, and unpaused.
Merely seeing an existing DAG is insufficient. Function-only changes may leave
the DAG version number unchanged, so version increment alone is not used.
On parse failure/timeout the original backup is restored and no corrected run
is triggered. Rollback refuses to overwrite another writer's newer changes.
Rollback's subsequent Airflow re-parse remains pending and is stated in the audit.

After recognition the existing allowlisted executor triggers with `conf={}`.
Verification requires the returned run ID, successful DAG, the expected successful
task, matching run DAG-version ID, and unchanged local/parsed reviewed source.
Execution or verification failure never starts an automatic retry/patch loop and
does not automatically roll back a run that has already been triggered.

## Persistence and API

`SourceRemediation` wraps the existing `ChangeProposal`/`SourceCodeChange`. It adds
proposal ID, DAG/function, original/base hash, original proposal, reviewed hash,
revision history, validation checks, exact approval, evidence, tests, timestamps,
backup, parse result, run ID, verification, feedback reference and audit events.
`SourceRevision`, `SourceValidation`, `SourceApproval`, `SourceAuditEvent` and
`SourceRemediationState` are defined in the existing change-model module.

Data lives in `data/source_remediations.json`, backups in `data/source_backups`,
and evaluation in the existing `data/remediation_feedback.json`. JSON writes are
atomic with a process lock; corrupt history is not silently overwritten. Run one
backend process. GET/list can read progress while execution polls Airflow. A second
execute cannot claim the same record or another active record for the same DAG.
Interrupted active records intentionally block further execution; inspect backup,
source and actual Airflow run state before manual reconciliation. No automatic
restart replay is attempted.

| Endpoint | Purpose |
| --- | --- |
| `POST /developer/chat` | Existing investigation; new demo may return `code_change.source_remediation_id` |
| `GET /source-remediations` | Persisted review/audit records |
| `GET /source-remediations/{id}` | Resume exact saved review and execution state |
| `PUT /source-remediations/{id}/source` | Save source, recalculate diff, invalidate approval |
| `POST /source-remediations/{id}/reset` | Restore original proposal as a new revision |
| `POST /source-remediations/{id}/validate` | Read-only validation |
| `POST /source-remediations/{id}/approve` | Exact revision/hash L2/ADMIN approval |
| `POST /source-remediations/{id}/reject` | Reject and clear approval |
| `POST /source-remediations/{id}/execute` | Explicit apply → parse → trigger → verify |
| `GET/POST /source-remediations/{id}/feedback` | Existing evaluation schema, linked to terminal remediation |

Mutation bodies include `revision` and `source_hash` (the reviewed proposal hash).
Source edits add `proposed_source`, `edited_by`; approvals add `approved_by`,
`approver_role`. No API accepts an arbitrary write path. Unknown IDs return 404,
state/revision conflicts 409, schema errors 422. Feedback is first-submission-wins.

## State machine

`proposed → edited (optional) → validated → approved → applying → applied →
airflow_validating → executing → verifying → succeeded`.

Edits from review states return to `edited`; revalidation resets approval.
Review failures use `validation_failed`; rejection uses `rejected`.
Execution outcomes include `stale_source`, `apply_failed`, `airflow_parse_failed`,
`apply_failed_rolled_back`, `execution_failed`, `verification_failed`.
Successful rollback retains the preceding parse-failure event in audit. Terminal
records cannot execute again; start a fresh investigation. All mutations are
persisted with revision-specific audit events.

## One manual live test (PowerShell)

Start Airflow, backend and frontend as described in [supervisor-demo.md](supervisor-demo.md).
Do not run the reset command concurrently with an active remediation or tests.
The reset intentionally restores the known bug in **only** the new demo; it backs
up any existing contents first. It accepts no arbitrary destination arguments.

```powershell
cd D:\Projects\airflow-support-intelligence
.venv/Scripts/python.exe -B scripts/reset_code_remediation_demo.py --confirm-reset

$dag = 'support_intelligence_code_remediation_demo'
$auth = Invoke-RestMethod -Method Post -Uri 'http://localhost:8088/auth/token' -ContentType 'application/json' -Body '{"username":"airflow","password":"airflow"}'
$headers = @{ Authorization = "Bearer $($auth.access_token)" }
# Use your configured Airflow credentials if the local defaults were changed.
# Wait for the new buggy source to appear before triggering.
$parsed = Invoke-RestMethod -Headers $headers -Uri "http://localhost:8088/api/v2/dagSources/$dag"
$parsed.content
$failure = Invoke-RestMethod -Method Post -Headers $headers -Uri "http://localhost:8088/api/v2/dags/$dag/dagRuns" -ContentType 'application/json' -Body '{"logical_date":null,"conf":{}}'
$failure.dag_run_id
```

Wait for the actual TypeError failure in Airflow. In the dashboard select this
DAG, Analyze Live Airflow, then ask Developer Copilot to fix the transaction
amount defect. Inspect actual exception/log/timeline evidence and provenance.
Click Review Proposed Change. Edit the proposed function (for example replace
the list's `record["amount"]` with `record.get("amount")`), Save Reviewed Version,
then Validate Changes. Check the backend diff and revision hash, enter your name,
approve that revision, then explicitly Execute Approved Remediation. Observe
parse recognition, returned corrected run, task/DAG success, audit and feedback.
The local file should contain exactly the approved source; other DAGs must stay
unchanged. Run the reset command only when ready for another demo.

For an API-driven review of the same flow:

```powershell
$api = 'http://localhost:8000'
$chat = Invoke-RestMethod -Method Post -Uri "$api/developer/chat" -ContentType 'application/json' -Body (@{message='Fix the None transaction amount using real source and evidence'; dag_id=$dag} | ConvertTo-Json)
$id = $chat.code_change.source_remediation_id
$review = Invoke-RestMethod -Uri "$api/source-remediations/$id"
$edited = $review.change.source_code.proposed_code.Replace('record["amount"] for record in records', 'record.get("amount") for record in records')
$review = Invoke-RestMethod -Method Put -Uri "$api/source-remediations/$id/source" -ContentType 'application/json' -Body (@{revision=$review.revision; source_hash=$review.proposal_hash; proposed_source=$edited; edited_by='YOUR NAME'} | ConvertTo-Json)
$version = @{revision=$review.revision; source_hash=$review.proposal_hash}
$review = Invoke-RestMethod -Method Post -Uri "$api/source-remediations/$id/validate" -ContentType 'application/json' -Body ($version | ConvertTo-Json)
$review.change.unified_diff
$review.validation
# Stop and personally review the exact code, diff, revision and hash here.
# Only after you approve that concrete version:
$review = Invoke-RestMethod -Method Post -Uri "$api/source-remediations/$id/approve" -ContentType 'application/json' -Body (@{revision=$review.revision; source_hash=$review.proposal_hash; approved_by='YOUR NAME'; approver_role='L2'} | ConvertTo-Json)
$result = Invoke-RestMethod -Method Post -Uri "$api/source-remediations/$id/execute" -ContentType 'application/json' -Body ($version | ConvertTo-Json) -TimeoutSec 300
$result.state
$result.verification
# Submit your own assessment after checking the result:
Invoke-RestMethod -Method Post -Uri "$api/source-remediations/$id/feedback" -ContentType 'application/json' -Body '{"useful":true,"change_quality":"correct","comment":"Reviewed live result"}'
```

## Implementation inventory

Created: `demo_dags/support_intelligence_code_remediation_demo.py`,
`scripts/reset_code_remediation_demo.py`, `backend/app/source_validation.py`,
`source_remediation_store.py`, `source_updater.py`, `source_airflow.py`,
`source_remediation.py`, `source_remediation_api.py`,
`frontend/src/SourceRemediationWorkspace.jsx`, `frontend/src/SourceRemediationHistory.jsx`, `tests/test_source_remediation.py`,
`tests/test_source_browser.py`, and this document.

Modified: `change_models.py`, `developer_models.py`, `developer_copilot.py`,
`source_patch_generator.py`, `main.py`, `frontend/src/App.jsx`,
`frontend/src/EngineerFeedback.jsx`, `tests/conftest.py`, `.gitignore`, and
`docs/supervisor-demo.md`. No visual redesign or new provider implementation.

## Verification record and limitations

2026-10-04: baseline 125 passed / 2 optional browser tests skipped. After changes,
156 backend tests passed / 3 optional browser tests skipped; frontend lint and
production build passed; all 3 opt-in Chrome browser scenarios passed. Four
existing dependency deprecation warnings remain. The session-wide read-only
fingerprint guard confirmed real Airflow Python DAG files were unchanged during
automated tests. Unit/integration/browser source writes use temporary DAG roots.

Live Airflow: the new demo was intentionally installed outside the test suite.
Run `manual__2026-10-04T05:49:47.698517+00:00` failed naturally with
`TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'`.
The normal Copilot pipeline retrieved that evidence and prepared/validated a
saved edited revision. Gemini returned HTTP errors even outside the sandbox;
the live proposal is explicitly `controlled_fallback`. Real cloud-generated
patch acceptance has **not** been demonstrated; structured AI success is tested
with mocked provider responses.

Live source remediation also passed, separately from mocked integration tests.
The engineer explicitly approved proposal `e7940123-d147-469b-a6aa-5282737aea5a`,
revision 2, SHA-256 `cd177420b2ca7c9a799b967b0e07ae365a5a245c3915116566dbe2dd14904a01`.
It was backed up, atomically applied, recognized by Airflow at
`2026-10-04T05:56:48.052673Z`, then triggered with empty configuration.
Corrected run `manual__2026-10-04T05:56:48.574910+00:00` and task
`summarize_transactions` succeeded and its real task log reported
`Transaction total: 200.0` / returned value `200.0`; verification matched the local/parsed source
and DAG version. Every other DAG file's hash remained unchanged. The live demo
is currently corrected, ready for the explicit reset before another presentation.
Audit and backup are persisted in the locations above. In the dashboard select
the code-remediation demo and use Saved source reviews to reopen this result.
The engineer then explicitly submitted **Useful — Correct**. That assessment is
saved under feedback ID `a85b314e-d59c-460d-9708-217be41e9e9f` and linked to the
live remediation. No user assessment was invented.

Remaining boundaries: trusted local single-process PoC, no authentication or
distributed locks, no OS-wide protection against concurrent external filesystem
writers, no atomic Airflow source pinning API, no durable background job queue.
Network-trigger ambiguity is reported and never automatically retried. Airflow
3 source/details/version capabilities are required; unsupported environments
fail closed. Stop external edits during this controlled demonstration. The AST
policy is intentionally narrow; other DAGs need explicit policy and tests before
source application can be enabled. The synchronous execute endpoint can take
several minutes; progress remains available via GET.
