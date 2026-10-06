# General source remediation for newly added DAGs

Updated 2026-10-06. This supersedes the two-DAG execution restriction described
in earlier demo and UI handoff reports. The normal AI proposal, review, approval
and source-execution path no longer selects behavior by a registered demo name.

## Supported workflow

Add a Python DAG at `AIRFLOW_DAG_SOURCE_ROOT/<dag_id>.py` (default:
`D:\Projects\airflow\dags`). No backend registry edit is needed. The file must
declare one static matching DAG ID and map the affected task's static `task_id`
through `python_callable` to one existing top-level function in that file.
Other tasks may be present; the edited callable cannot be shared by multiple tasks.

The same pipeline now supports a new shipment-region DAG, order-metrics DAG or
memory-processing DAG when its actual source/proposal meets these conditions.
There is no exception-name-to-patch selector. A working configured provider must
produce a valid proposal; unavailable/invalid AI does not create a generic fix.

1. Restart the backend to load the new policy; refresh the frontend.
2. Add your DAG to the configured local directory and wait for Airflow to parse it.
3. Trigger the initial failure yourself and wait for a terminal failed run.
4. Open **Incidents**, refresh the catalog, open that DAG and **Analyze Live Airflow**.
5. In **Developer Copilot**, request an evidence-grounded correction, including
   the intended business behavior for invalid input. Leave demo fallback unchecked.
6. Follow the **new response's Review Proposed Change** link. Review/edit and save.
7. Validate. Inspect the checks, source diff, revision and hash; approve as a named
   L2/ADMIN reviewer only after reviewing the actual behavior.
8. In **Execution & feedback**, explicitly confirm execution. This confirmation
   authorizes both the source write and a new run with empty configuration `{}`.
9. Inspect backup/application, Airflow parse recognition, corrected run and task
   verification. Check business results in Airflow logs; syntax validation alone
   does not prove business correctness. Submit feedback and reopen the saved review.

Do not use the synthetic reset script for a new DAG: that script still restores
only its two bundled test fixtures. Install new DAG source yourself. No real DAG
was installed, reset or executed as part of implementing this change.

## Policy and safeguards

`source_execution_policy.py` derives eligibility from actual source and task
mapping. The model reports `execution_allowed` and `execution_block_reason`; the
service/updater independently recheck policy before approval and application.
The flag is not an authorization token.

- Source stays inside the configured trusted root; client-supplied paths,
  traversal, symlinks and junctions are rejected.
- Only one existing function body may change. Imports, DAG/task declarations,
  decorators, signature and return annotation remain intact.
- Existing literal input datasets are preserved so a proposal cannot simply
  remove the failing example. New dynamic-code and certain filesystem/process
  operations, dunder access and function-local imports/global mutations are blocked.
- Syntax and AST checks never import or execute proposed source. These checks
  are not a security sandbox or exhaustive side-effect analysis. Engineers must
  review code that will run with Airflow's existing credentials and permissions.
- Exact revision/hash validation and named human approval remain mandatory.
  Editing invalidates both. Source fingerprints are rechecked before application.
- Original bytes are backed up before atomic replacement. Airflow must expose
  matching source, the expected filename and a newer healthy parse before triggering.
- The returned run must use the recognized DAG version. The targeted task must
  succeed, the DAG must succeed, and other reported tasks must be success/skipped.
- Parse failure attempts guarded rollback before any trigger. Execution or result
  failures do not silently retry, generate another patch or roll back a running DAG.
- Audit, feedback, concurrency exclusion and duplicate-execution guards are retained.

## Existing records

New proposals carry execution policy version 2. Older JSON records default to
version 1 and remain readable, including completed results and feedback. Their old
approvals do not gain new permissions. Start a **new investigation and proposal**
to use the generalized workflow; do not edit the stored policy version manually.

The model's new fields are additive; existing endpoint URLs and action request
payloads are unchanged. Old records require no destructive migration.

## What remains deliberately unsupported

This is a general **single-file, mapped Python callable** workflow, not automatic
repair of every possible Airflow deployment. Dynamic/generated DAG identities,
multiple DAGs in one file, imported/shared callables, TaskFlow/nested-callable
layouts without an explicit local mapping, and multiple-file/import changes are
not automatically executable. Filename must match DAG ID. The UI explains blocked
policy eligibility; unsupported cases require manual source review.

Verification currently triggers with `{}`. DAGs requiring runtime parameters or
unsafe-to-repeat external effects need a separately designed execution plan; do
not approve a run that is inappropriate for that DAG. Paused/stale/unparsed DAGs
remain blocked. Local reviewer identity is self-declared in this PoC. JSON stores
still assume one backend process. No authenticated multi-user deployment or Python
execution sandbox was added.

## Implementation and testing

Production changes: `source_execution_policy.py`, `source_remediation.py`,
`source_updater.py`, `source_airflow.py`, `change_models.py` and the review UI.
The legacy `source_validation.py` registry is retained only for explicit synthetic
fallback/reset tooling; it is no longer consulted for normal apply eligibility.
No new dependencies, model retraining or live provider call were required.

Regression coverage includes randomly generated DAG names, arbitrary mapped task
names, multiple tasks, proposal/edit/approval/backup/apply/verification/feedback,
legacy approvals, forged flags, task mismatch, ambiguous source, traversal, stale
source, rollback and existing demo workflows. The browser suite includes a newly
named DAG using a simulated structured AI response rather than a demo fallback.
External Airflow/provider boundaries are simulated, and all test writes use
temporary roots. This verifies orchestration; it is not a live-provider acceptance run.

Final verification on 2026-10-06: **260 passed, 0 failed, 0 skipped** in 84.21 seconds
(250 backend/non-browser and 10 browser cases), with four existing dependency
deprecation warnings. Frontend ESLint and Vite production build passed.
`git diff --check` passed. The real-DAG before/after fingerprint guard passed.
Machine-readable results: `.test-runs/general-workflow-results.xml`.

```powershell
$env:RUN_BROWSER_TESTS = '1'
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider --basetemp=.test-runs/general-workflow-all --tb=short --junitxml=.test-runs/general-workflow-results.xml
cd frontend
npm.cmd run lint
npm.cmd run build
```
