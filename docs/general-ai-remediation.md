# General AI source investigation: continuation report

> Current execution policy: [General source remediation](general-source-execution.md).
> The historical two-demo write restriction below has been superseded for new proposals.


Verified on 2026-10-05. The interrupted implementation was continued in place.
Existing classification, source execution, action history and unrelated
uncommitted changes were preserved. No UI redesign or new demo DAG was added.

**Yes: the real Gemini provider generated a source-code remediation proposal.**
`gemini-3.5-flash-lite` returned `DeveloperRemediationResponse`, passed the same
Pydantic parsing and source-composition checks used by Copilot, and produced
`developer_llm` provenance. The saved proposal subsequently passed all five
review validation checks. It remains unapproved and unapplied.

## Investigation and proposal architecture

The normal path is:

```text
Failed task + actual Airflow evidence/logs/timeline + safely resolved source
  -> general structured Developer LLM investigation
  -> diagnosis / root cause / reasoning / evidence / risks / assumptions
  -> untrusted function proposal
  -> in-memory composition + syntax/structural checks
  -> saved editable review + authoritative diff/revision/hash
  -> validation
  -> separate source execution policy + exact-version human approval
  -> explicit execution (backup / atomic apply / reparse / trigger / verify)
```

`ai_source_investigation.py` sends the actual source and failed-task mapping,
developer request, exception/operator, run/task metadata, bounded real log
excerpt, timeline, ML, evidence signals and hybrid analysis. Classification does
not select code. `DeveloperRemediationResponse` forbids unknown fields and
requires status, diagnosis, root_cause, reasoning, evidence_used, target_function,
proposed_function, change_summary, tests_to_run, risks and assumptions.

The previous configuration/supervisor/Kubernetes hardcoded patch generators were
removed. There is no ordinary DAG-ID or exception-to-patch dispatcher. Tests use
three unrelated temporary DAGs with AttributeError, ZeroDivisionError and KeyError
and different mocked AI responses through the same `/developer/chat` pipeline.

The resolver currently requires `<dag_id>.py` directly under the configured root;
this does not support every possible Airflow source layout. A patch can replace
one existing top-level function. The task's mapped callable is enforced when
available. Unsupported or ambiguous source may yield investigation without code.

## Proposal permission versus execution permission

Any safely resolved failed DAG can receive an AI proposal, editable review,
revision history, backend diff and validation. History/workspace access does not
depend on the runtime-action recommendation or membership in the write allowlist.

Application remains restricted to these existing policies:

- `support_intelligence_code_remediation_demo`
- `support_intelligence_customer_discount_remediation_demo`

The order-metrics DAG remains outside that list. Backend approval rejects
unsupported targets. The updater independently checks write policy, including
when a forged approval is supplied in a test. The UI disables apply approval and
execution for those targets but retains editing and validation.

General structural validation preserves imports, DAG/task declarations, signature,
decorators and every other function. Traversal, outside-root targets, symlinks,
junctions and noncanonical whitespace identities are rejected. The model and
client cannot choose an application path. Validation compiles/inspects AST only;
it never executes proposed Python. Allowed demos retain their additional
baseline, input-fixture and conservative AST/call restrictions.

Saved edits increment revision, recalculate hash/diff, retain the original AI
proposal and clear validation/approval. Invalid drafts may be saved for editing
but cannot be approved. Execution still requires the exact revision/hash, current
base fingerprint, backup and explicit approval; parse rollback, empty-conf
trigger, source/run/task verification, audit and feedback are preserved.

## Provider diagnosis and configuration

The API key loaded successfully; no secret was printed. Authenticated model
discovery and model metadata returned HTTP 200. Listed models advertise methods,
but listing alone does not establish generation availability for this account.

| Model | Actual structured generation result |
| --- | --- |
| `gemini-2.5-flash` | HTTP 404, `NOT_FOUND`: unavailable to new users; provider suggested `gemini-3.8-flash` |
| `gemini-3.8-flash` | HTTP 503, `UNAVAILABLE`: high demand, on both checked attempts |
| `gemini-3.7-flash` | Read timeout at the existing 30-second read limit |
| `gemini-3.5-flash-lite` | First response passed schema parsing but failed Python syntax; final explicit test produced the valid proposal below |

Requests use `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`,
the `x-goog-api-key` header, `responseMimeType=application/json` and
`responseJsonSchema`. The successful request verifies this endpoint/schema
combination for the tested model/account. Connection/read timeouts remain 5/30
seconds, with no automatic retry. The separate diagnostic attempts above were
explicit checks, not an application retry loop. Availability and model output
quality can still vary on later requests.

Only `GEMINI_MODEL` was changed in local `.env`, to `gemini-3.5-flash-lite`;
credentials and other settings were preserved. `.env.example` and setup docs now
use that verified model. An explicit setting overrides the older transport default.
Provider status, model, safe HTTP category/message and proposal provenance appear
in Copilot. Failure is never converted into AI success.

## Demo fallback

Default: disabled. `allow_demo_fallback=true` (the explicit UI checkbox) enables
the isolated two-demo infrastructure fallback if the provider cannot produce a
valid proposal. Its label is `controlled_demo_fallback`, visibly not AI generated.
Arbitrary DAGs never get such a fallback. A model's explicit `no_proposal` decision
is respected even with opt-in. Legacy `controlled_fallback` records remain
readable for historical audit only. The real acceptance preparation used no fallback.

## Exact live preparation result

- DAG: `support_intelligence_customer_discount_remediation_demo`
- Existing failed run: `manual__2026-10-04T12:15:29.314010+00:00`
- Task: `calculate_customer_discounts`; `PythonOperator`
- Exception: `AttributeError`, `'NoneType' object has no attribute 'lower'`
- Copilot classification: `Application Code`
- Provider/model: Gemini / `gemini-3.5-flash-lite`
- Provenance: **`developer_llm`**
- Proposal: `7921ac6b-88ea-4107-9298-8d72e9a172f8`, revision **1**
- Reviewed SHA-256: `29985ad68d3aa075fd589a8762e157aca2bbf855761aaff5563dafaa94de8dbb`
- State: **validated**; approval, applied timestamp and triggered run ID: **null**

The exact model-generated diff is:

```diff
-        normalized_tier = tier.lower()
+        normalized_tier = tier.lower() if tier is not None else ""
```

Diagnosis and reasoning identify the None tier in CUST-1003. Evidence includes the
real exception, failed task and actual source fixture. Its stated assumption is
that a missing tier takes the existing zero-discount branch. This proposal handles
None; it does not establish behavior for arbitrary other non-string tiers. The
model's risk statement and suggested test command are advisory, not verified
business guarantees. No suggested command or proposed function was executed.

Syntax, DAG structure/policy, target path, intended file and unchanged source all
passed. Airflow is unpaused, not stale, has no import errors, and still serves the
same buggy source. The only observed run is the existing failed run above.
Customer source SHA-256 remains
`32c4873b1a7b0523e93cbdb15afc33a870f2aad83472828c9163326e3d5f1ead`.
Automated test sessions assert all real Python DAG fingerprints match before/after;
the additional live readiness check also matched every real DAG fingerprint.

Local ignored evidence: `.test-runs/general-provider-result.json`,
`gemini-model-discovery.json`, `gemini-flash-lite-invalid-source.json`,
`customer-ai-readiness.json`, and `customer-ai-proposal.diff`.
The one-shot migration scripts `isolate_demo_fallback.py` and
`refactor_copilot_source.py` were removed. Read-only provider/readiness diagnostics
were intentionally retained under ignored `.test-runs`; they are not application code.

## Verification

Final focused suite: **157 passed** (13.27 seconds). Complete backend suite:
**232 passed, 4 skipped** (17.01 seconds). The four skipped opt-in browser cases
were run separately: **4 passed** (32.30 seconds). The dedicated general proposal
file contains **23 passing cases**. All **28 real Python DAG files** retained
their fingerprints, including the final read-only check after regression.
Frontend ESLint and Vite production build passed. Four opt-in browser scenarios
passed against temporary stores, mocked AI/provider boundaries and simulated
Airflow, including source editing/approval/execution/feedback and runtime recovery.
Browser success is not a claim of live source execution. Four existing dependency
deprecation warnings remain. `git diff --check` passed with line-ending notices.

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_general_source_investigation.py tests/test_source_review.py tests/test_source_remediation.py tests/test_customer_discount_remediation.py tests/test_application_code.py tests/test_hybrid_analyzer.py tests/test_supervisor_demo.py tests/test_llm_providers.py -q -p no:cacheprovider --basetemp=.test-runs/general-final-focused-pass --tb=short
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider --basetemp=.test-runs/general-final-full-pass --tb=short
cd frontend
npm.cmd run lint
npm.cmd run build
cd ..
$env:RUN_BROWSER_TESTS='1'
.venv/Scripts/python.exe -B -m pytest tests/test_demo_browser.py tests/test_source_browser.py -q -p no:cacheprovider --basetemp=.test-runs/general-resume-browser-final --tb=short
Remove-Item Env:RUN_BROWSER_TESTS
```

## Next manual customer-discount acceptance steps

1. Restart your existing backend with the verified provider configuration:

   ```powershell
   cd D:\Projects\airflow-support-intelligence
   $env:LLM_PROVIDER='gemini'
   $env:GEMINI_MODEL='gemini-3.5-flash-lite'
   .venv/Scripts/python.exe -B -m uvicorn backend.app.main:app --reload --env-file .env
   ```

   Keep one backend process. Refresh the existing frontend (or start it with
   `npm.cmd run dev` in `frontend`). The Gemini key stays in your local `.env`.

2. Select `support_intelligence_customer_discount_remediation_demo` and click
   **Analyze Live Airflow**. The existing failed run can be reused; no reset or
   new trigger is needed for the currently verified buggy state. If you want a
   complete fresh demonstration, perform the optional reset and `{}` trigger
   yourself using [the existing customer-demo instructions](customer-discount-remediation.md).

3. Leave **Allow labelled demo fallback** unchecked. Ask: **Investigate this
   failure and propose a source-code correction.** Require provider success and
   `developer_llm` provenance. Review diagnosis, root cause, evidence, reasoning,
   tests, risks and assumptions. If a new request fails, inspect the provider
   diagnostics; it is not an AI success. The already verified saved proposal can
   also be opened from **Saved source reviews** for this DAG.

4. Open **Review Proposed Change**. Inspect current/proposed source and the diff.
   Edit if desired; **Save Reviewed Version** must update revision/hash/diff and
   clear validation and approval. **Reset to AI Proposal** preserves audit history.

5. **Validate Changes** and inspect every check. Syntax validation does not prove
   business correctness. Review the None handling, original fixture and expected
   customer results (400.0, 270.0, 250.0; three processed customers).

6. Only after your review, enter your name/role and **Approve Reviewed Change**
   for the exact current revision/hash. Then explicitly choose **Execute Approved
   Remediation** yourself. This is the point where the live source may be written.

7. Inspect backup/audit, exact source application, Airflow reparse recognition,
   the returned corrected run with `conf={}`, expected task/DAG success and
   source/version matching. Inspect actual business results in task logs, then
   submit Engineer Feedback. No live step from approval onward was performed here.
