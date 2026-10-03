# Supervisor demo: source review, controlled runtime recovery, feedback

This is a controlled synthetic demonstration. Source proposals are review-only;
runtime recovery triggers a new DAG run with `dag_run.conf`. These are separate
operations. Feedback records evaluation without retraining or executing anything.

## Start the existing services

Airflow is the separate project at `D:\Projects\airflow`. Its existing Compose
stack exposes Airflow on `http://localhost:8088`. If necessary, start that stack:

```powershell
cd D:\Projects\airflow
docker compose up -d
```

Backend, from a separate terminal:

```powershell
cd D:\Projects\airflow-support-intelligence
.venv/Scripts/python.exe -m uvicorn backend.app.main:app --reload --env-file .env
```

Frontend, from another terminal:

```powershell
cd D:\Projects\airflow-support-intelligence\frontend
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`).
Keep the backend as one process for the JSON stores. Existing shell variables
override `.env`. The source directory defaults to the sibling `airflow/dags`;
`AIRFLOW_DAG_SOURCE_ROOT` can override it at startup. A container deployment needs
an explicit read-only mount of the DAG directory and the corresponding setting.

For a demo independent of cloud availability, use `LLM_PROVIDER=none` before
starting the backend. Otherwise keep your configured Gemini provider; provider
failures fall back to evidence reasoning. See [LLM setup](llm-setup.md).

## Demonstrate the complete flow

1. In Airflow, select `support_intelligence_configuration_review_demo`. If paused,
   unpause it using Airflow's UI. Trigger it with `{"mode":"failure"}` and wait
   for the run to fail. This DAG intentionally reports invalid configuration.
2. In the support dashboard, select that same DAG under **Live Airflow Incident**
   and click **Analyze Live Airflow**. Automatic detection may already select it.
3. Show the observed exception, evidence signals, and timestamped incident
   timeline. Explain the ML/SHAP result only when the required features exist;
   missing features should stay visible rather than being invented.
4. In **Developer Copilot**, ask: “Why did the configuration task fail, and what
   should I review before changing it?” Click **Send**.
5. Under **Proposed Source-Level Correction**, point out **CONTROLLED FALLBACK ·
   REVIEW ONLY**. The replacement is a deterministic demo template, not an
   AI-generated patch.
6. Click **Review Proposed Change**. In **Source Code Change Review**, show the
   target, path, complete current DAG, complete proposed DAG, and exact Git-style
   diff with additions/deletions. Imports, task declaration, and DAG declaration
   are retained. There is no source execution button.
7. Move to **Controlled Runtime Recovery**. Click **Create Remediation Action**.
   Creation runs existing policy/catalog validation and initially proposes
   `mode=failure`; it does not execute anything.
8. Click **Edit Action**, select **Recovery Mode → recovery**, and click **Save
   Changes**. Saving revalidates the action and clears any previous approval.
9. Inspect **Runtime Configuration Change**: `mode=failure` → `mode=recovery`.
   This changes the configuration sent to a new DAG run, not the Python source.
10. The engineer clicks **Approve Action**, then **Execute Approved Action**.
    These controls belong only to runtime recovery. The existing executor sends
    the allowlisted `trigger_dag` request and verification checks the returned run.
11. Wait for **Execution & Verification** to report `verified` and `success`.
    A failed execution also reaches a terminal state and allows feedback.
12. In **Engineer Feedback**, choose Useful/Not Useful, a quality value, and an
    optional comment. Click **Submit Feedback** and show **Feedback saved
    successfully**. The saved record is linked to the action ID.

## Feedback contract

- `POST /actions/{action_id}/feedback` accepts required `useful` (a JSON boolean),
  required `change_quality` (`correct`, `partially_correct`, `incorrect`), and an
  optional `comment` (up to 4,000 characters).
- Only actions with status `succeeded` or `failed` accept feedback; other states
  return 409. Unknown actions return 404; malformed input returns 422.
- `GET /actions/{action_id}/feedback` returns the saved record or `null`.
- First submission wins per action. Retrying returns that same record; it cannot
  overwrite an evaluation or create an accidental duplicate.
- Records live in `data/remediation_feedback.json`. Missing files are supported;
  invalid existing files return 503 rather than silently losing records.
- Writes are atomic and locked within one backend process. Multiple independent
  worker processes writing the same JSON file are outside this PoC's scope.
- Identity follows the current demo convention (`l1-user`), not authenticated
  production identity. Existing role checking is also a PoC boundary.

## Accurate claims and remaining boundaries

- Source retrieval, AST replacement, and diff generation never write or execute
  DAG source. Source proposals are additionally rejected by the action service's
  execution entry point if attached to an action.
- All three supported demo templates now use actual current source. Missing
  files, missing functions, invalid syntax, mismatched signatures, or absent
  generators return no reviewed proposal while analysis remains available.
- Read-only source resolution is not restricted to those demo templates. It
  follows the `<dag_id>.py` convention inside the configured root and rejects
  path traversal. DAG IDs that differ from filenames need future mapping work.
- The supervisor-demo source file must actually exist to produce its proposal;
  an absent file no longer produces a fabricated current-code snapshot.
- Dynamic LLM patch generation was intentionally skipped. Optional LLM diagnosis
  remains available, but cannot overwrite a controlled proposal's evidence/reason.
- Kubernetes signals in this demo are from controlled task evidence, not a new
  live Kubernetes integration. SHAP explains model contributions, not causation.
- Runtime approval, action policy, executor allowlisting, and verification remain
  in place. Retry/clear/pause/unpause execution is still disabled as before.
- Feedback never changes approval, executes recovery, edits DAGs, or retrains.

## Verification commands

The initial backend baseline was 77 passing tests. New tests isolate JSON stores
so future test runs do not add actions or feedback to the engineer's history.

```powershell
cd D:\Projects\airflow-support-intelligence
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider
cd frontend
npm run lint
npm run build
```

Optional headless browser tests require Chrome and Playwright in the virtual
environment. They serve the built UI, use real FastAPI routes with isolated
stores, and simulate only the Airflow boundary; they never trigger a live DAG.

```powershell
cd D:\Projects\airflow-support-intelligence
.venv/Scripts/python.exe -m pip install playwright
$env:RUN_BROWSER_TESTS = "1"
.venv/Scripts/python.exe -B -m pytest tests/test_demo_browser.py -q -p no:cacheprovider
Remove-Item Env:RUN_BROWSER_TESTS
```

Browser coverage includes successful recovery, execution errors, review-only
source UI, human approval before execution, feedback validation, saved feedback,
and disabled duplicate submission. Screenshots are saved in pytest's temporary
test directories. Live recovery still requires the engineer's approval above.

## Implementation inventory

Created:

- `backend/app/feedback_store.py`
- `frontend/src/EngineerFeedback.jsx`
- `frontend/src/UnifiedDiff.jsx`
- `tests/conftest.py`
- `tests/test_feedback.py`
- `tests/test_source_review.py`
- `tests/test_supervisor_demo.py`
- `tests/test_demo_browser.py`
- `docs/supervisor-demo.md`

Updated:

- `backend/app/feedback_models.py`, `backend/app/main.py`: feedback contract/API.
- `backend/app/source_resolver.py`, `backend/app/source_change_provider.py`,
  `backend/app/source_patch_generator.py`: actual source and validated composition.
- `backend/app/developer_copilot.py`, `backend/app/developer_models.py`,
  `backend/app/change_models.py`, `backend/app/change_review.py`: provenance and
  graceful no-proposal state while retaining incident evidence.
- `backend/app/action_service.py`: explicit source-review execution guard.
- `frontend/src/App.jsx`, `frontend/src/index.css`: terminology, shared diff,
  feedback integration, failed-execution state refresh, and existing lint fixes.
- `tests/test_llm_providers.py`: isolate the quota regression's source fixture.
- `.env.example`, `.gitignore`, `README.md`: configuration and demo documentation.
