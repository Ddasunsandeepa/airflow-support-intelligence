# Operations console redesign: final handoff

> Current execution policy: [General source remediation](general-source-execution.md).
> The historical two-demo write restriction below has been superseded for new proposals.


Verified on 2026-10-06. The interrupted implementation was retained, inspected and
completed. Existing source-remediation work, action history and unrelated
uncommitted changes were preserved. The continuation added final browser assertions,
screenshots and this report; it did not restart the frontend or change the AI
remediation architecture. The original contract inventory is in
[ui-redesign-audit.md](ui-redesign-audit.md).

## A. Old UX problems found

The old App component combined selection, evidence, chat, action review and execution
in one long page. Manual inputs dominated the landing screen. Feedback could appear
permanently disabled without explaining its required fields. Persisted proposals
were not followed by list refreshes. Selection changes could retain another DAG's
action/chat state, and an older analysis response could replace newer context.
Runtime configuration assumed a recovery-mode contract that some DAGs do not have.

## B. New information architecture

A persistent sidebar and top bar surround an operations workspace. Overview shows
actual API/catalog availability, registered DAG counts, session investigations and
persisted source activity. Incidents provides search, state/classification filters
and sorting. Classification, task and exception values remain unavailable until
analysis supplies them. Investigation separates observed evidence from interpretation;
Copilot, operational remediation and persisted source reviews have distinct views.
Manual ML evidence entry remains available as a separate tool.

## C. Routes and navigation

| Hash route | Purpose |
| --- | --- |
| `#/overview` | Operations overview |
| `#/incidents` | Registered DAGs and import errors |
| `#/incidents/{dag or import_error}/{encoded ID}/investigation` | Summary, Timeline, Evidence, Intelligence, Runbook |
| `#/incidents/{type}/{encoded ID}/copilot` | Incident-specific Developer Copilot |
| `#/incidents/{type}/{encoded ID}/remediation` | Source investigation and operational actions |
| `#/reviews` | Persisted source reviews across DAGs |
| `#/reviews?dag={encoded DAG ID}` | Source reviews for one DAG |
| `#/reviews/{proposal ID}` | Reopen a saved review and its result |
| `#/audit` | Persisted source audit activity and feedback references |
| `#/manual` | Manual evidence analysis |

Hash routes support browser back/forward and review reloads without server rewrite
configuration. Sidebar incident links use the current/last analyzed incident; without
context they ask the engineer to choose an incident.

## D. Major component changes

| File under frontend/src | Responsibility |
| --- | --- |
| `App.jsx` | Shell, routes, health/catalog/detection, session observations |
| `api.js` | JSON requests, abortable resource loading, focus/mutation/interval refresh |
| `ConsolePages.jsx` | Overview, searchable catalog, manual evidence |
| `IncidentWorkspace.jsx` | Incident/run context, analysis lifetime, workspace tabs |
| `Investigation.jsx` | Evidence, timeline, hybrid attribution, SHAP details and runbook |
| `Copilot.jsx`, `CopilotInvestigation.jsx` | Scoped conversation, provider diagnostics, proposal link |
| `RuntimeRemediation.jsx` | Configuration review, operational approval/execution and feedback |
| `SourceRemediationHistory.jsx` | Persisted review table, filtering and audit navigation |
| `SourceRemediationWorkspace.jsx` | Source editing, authoritative diff, validation, approval, execution/result |
| `EngineerFeedback.jsx` | Required fields, eligibility, submission, error/retry and persisted feedback |
| `Lifecycle.jsx`, `ui.jsx`, `UnifiedDiff.jsx` | Evidence-backed progress, shared controls/dialogs and diff rendering |
| `index.css` | Neutral light surfaces, restrained dark navigation, responsive tables/editors and focus styles |

The obsolete Vite starter `App.css` was removed during the redesign. Final inspection
found no remaining frontend TODO/FIXME, console.log or debugger statements. Build
output, current QA screenshots and test reports remain intentionally ignored under
`frontend/dist` and `.test-runs`; older live-review artifacts were preserved because
they belong to previous work. No indiscriminate cleanup of uncommitted files occurred.

## E. Engineer Feedback

The backend already accepted valid payloads. The demonstrated problem was frontend
state and affordance: usefulness AND change quality are required, but the disabled
button did not explain that; state could survive a resource change; load/submit
failures lacked a clear recovery flow. No backend validation was weakened.

The form is now keyed by resource and action/proposal ID. It explains missing
usefulness/quality, accepts an optional comment, and enables Submit Feedback once
required fields are valid and saved-state loading has succeeded. Terminal eligibility,
in-flight protection and duplicate semantics remain intact. Errors are visible.
Retry reloads saved feedback before permitting another submission, covering uncertain
POST outcomes. Existing feedback replaces the form with its persisted assessment,
comment and timestamp. Duplicate API submissions return the first saved record.

Browser verification covers successful runtime/source feedback, missing quality,
explicit enabled-button assertion, optional comment persistence, POST failure/retry,
GET failure/retry, duplicate handling, nonterminal eligibility and page reload.

## F. Saved Source Reviews

Copilot already persisted valid proposals. The old list fetched on mount/DAG/manual
refresh, without invalidation after proposal creation; it also lacked stable review
navigation. This made saved reviews difficult to discover or resume.

Successful mutations now invalidate resource data. Lists also revalidate on focus,
mount and a 15-second interval. Stable proposal routes load backend state and source
afresh. Search/filter and empty/loading/error/retry states are explicit. Tests create
a proposal through Copilot, compare the list with persisted records, navigate away,
reopen and compare source/revision. Existing source workflows additionally save new
revisions, execute against temporary fixtures, reopen the completed result and reload
its persisted feedback. Saving reviewed source updates the existing proposal.

## G. Incident switching and stale state

The previous page kept independent action/chat/analysis variables across selection
changes, and analysis requests were not cancelled. Workspaces now remount by incident
type/ID; Copilot and runtime state are also keyed by analyzed run. Analysis uses an
AbortController and checks cancellation before updating state. Resource requests clear
data on a changed path and ignore obsolete responses. Runtime async callbacks check
component lifetime. Source reviews and feedback forms are keyed by their record IDs.

Browser checks cover leaving a source proposal, leaving a completed simulated runtime
action with saved feedback, and switching again while analysis is delayed. The new
incident does not show the prior classification, runtime action, proposal link,
feedback or recovery result. Returning to a source review loads its persisted record;
incident-local unsaved state is not treated as a backend record.

## H. Memory classification

The failure is a structured `MemoryError` reporting estimated memory usage of
139.42 MB above a configured 64 MB task limit. The generic Configuration rule matched
the substring `config` in `configured` before resource evidence. There was no explicit
MemoryError rule. Read-only source inspection found that the memory demo does not
consume `dag_run.conf`; changing mode cannot fix that implementation.

The narrow correction recognizes a structured MemoryError with a failed task ID as
Resource before generic configuration text. Direct DAG import, Kubernetes/container
and parsing evidence keep precedence. No DAG-ID-specific classifier was added. Genuine
configuration ValueErrors retain Configuration; other runtime recommendations remain.
The existing hybrid fallback is unchanged. API regression verifies Resource,
EVIDENCE_SIGNAL_FALLBACK, `resource.md` and no recommended runtime trigger. A browser
flow using that actual API response verifies the source-investigation presentation.

## I. Operational versus source remediation

Operational actions still use the existing action APIs and policy. JSON configuration
starts at `{}`; engineers supply configuration supported by their DAG. There is no
universal failure/recovery preset. Existing supported configuration-recovery browser
flows still pass. MemoryError and Application Code recommendations direct engineers
toward source/input investigation instead of offering a new runtime trigger.

Source proposal availability is separate from write eligibility. The current source
execution allowlist was not expanded: order-metrics and memory-processing remain
outside it. Review and read-only investigation do not imply permission to apply.

## J. Review, edit, diff, validation and approval

Source review has separate Source & diff, Diagnosis, Validation & approval,
Execution & feedback and Audit tabs. Current and proposed source are adjacent, with
internal scrolling. The saved revision's backend diff is authoritative. Revision,
SHA-256, provenance, validation and approval remain visible or expandable.

Unsaved edits disable execution and make validation/approval stale. Saving creates
the next reviewed revision. Approval and execution are separate native confirmation
dialogs naming the exact DAG, revision and hash. Cancel receives initial focus.
Backend validation, policy, source fingerprint, backup, approval and verification
guards remain authoritative. Lifecycle milestones derive from actual backend evidence;
later stages do not automatically claim all earlier stages occurred.

## K. Dependencies

No runtime dependencies were added or removed; React/Vite and existing manifests and
lockfiles were retained. Hash navigation and small fetch hooks avoid a framework
migration. Native dialogs and semantic controls avoid a new component/editor package.
Pinned Prettier was used as temporary formatting tooling in the earlier implementation;
it was not added to the application dependencies. Tests reuse existing pytest,
Playwright/Chrome and FastAPI TestClient tooling.

## L. Backend/API contracts

No HTTP routes or request/response schemas were changed by the redesign. Feedback and
source persistence endpoints retain their existing contracts. Backend behavioral
changes are limited to the explicit MemoryError evidence rule and passing optional
evidence into the internal `build_remediation_recommendation` helper to suppress the
inappropriate trigger recommendation. Earlier uncommitted AI/source-remediation APIs
were preserved and are not new redesign changes.

## M. Exact final test results

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Backend/non-browser regression cases | 236 | 0 | 0 |
| Browser/E2E cases (same complete run) | 9 | 0 | 0 |
| Complete pytest run | **245** | **0** | **0** |
| Frontend ESLint | command passed | 0 | n/a |
| Vite production build | command passed | 0 | n/a |
| git diff --check | passed | 0 | n/a |

Complete run: 63.44 seconds; four existing dependency deprecation warnings from
Starlette/AnyIO and SHAP/Matplotlib. JUnit evidence:
`.test-runs/ui-handoff-results.xml`. Browser cases comprise two runtime workflows,
two source workflows and five console scenarios. The console-only rerun also passed
5/5 before the complete rerun.

An earlier expanded run had three new test-assertion failures: HTML textarea CRLF
normalization, failing to refresh an already-loaded catalog after fault injection,
and an ambiguous selector also matching a hidden tab. These were corrected without
weakening application behavior or removing scenarios. The final complete run is green.
The initial sandbox build hit Windows subprocess EPERM; the authorized rerun passed.

Commands from the repository root:

```powershell
$env:RUN_BROWSER_TESTS = '1'
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider --basetemp=.test-runs/ui-handoff-final --tb=short --junitxml=.test-runs/ui-handoff-results.xml
cd frontend
npm.cmd run lint
npm.cmd run build
cd ..
git diff --check
```

## N. Visual QA

Actual Chrome screenshots were captured at 1920x1080, 1440x900 and 1366x768 and
inspected across the shell, Overview, Incidents, investigation, Copilot, review list,
source editor/diff and approval dialog. Summary, Timeline, Evidence, Intelligence
and Runbook each have captures. Additional captures cover feedback success/failure,
API/provider unavailability, review loading/empty/error and memory remediation.

Screenshots are in `.test-runs/ui-qa/`, named by view and viewport width. Examples:
`overview-1920.png`, `investigation-1440.png`, `source-review-1366.png`,
`approval-1366.png`, `feedback-saved.png`, `memory-remediation.png`.
Full-page captures can be taller than the viewport height.

QA checked wrapping of long DAG/run IDs and exception text, table containment,
editor height/scrolling, focus and button hierarchy. Browser assertions check no
document-level horizontal overflow in the catalog, source workspace and investigation
tabs. The earlier implementation's source header was reduced and repeated details
collapsed. No further visual redesign was necessary in this continuation.

## O. Safety

No real Airflow DAG was triggered, reset, approved, executed or modified during this
automated UI testing. Browser requests went through TestClient with simulated Airflow
and temporary source/store roots. Source workflow tests intentionally change only
temporary fixture files. Provider responses are mocked; no live LLM call was needed.
The session-wide before/after SHA-256 guard for local Python DAG files passed in the
final run; a read-only enumeration in this continuation found 15 such files under
`D:\Projects\airflow\dags`. No live action was performed as a safety check.

## P. Remaining limitations and opening the console

The backend catalog has no aggregate failed-run statistics, historical incident list,
provider-health endpoint, authenticated identities or global runtime-action list.
The UI labels missing data honestly. Audit navigation covers persisted source events;
runtime actions can be reopened by ID, but detailed runtime verification results are
not persisted by the existing action endpoint. Local reviewer roles are self-declared.

Latest-run analysis remains the existing API behavior. Session analysis/chat and
unsaved editor drafts are not persisted; save reviewed source before leaving its
workspace. Saved reviews and feedback do survive navigation/reload. The runbook
renderer supports a safe Markdown subset, and SHAP remains available in expandable
details. Validation here used desktop Chrome and simulated external services, not
a new live Airflow remediation, mobile audit or fresh cloud-provider acceptance run.

Start/reuse the project's existing backend and Vite development server, then open
`http://localhost:5173/#/overview` (use Vite's printed port if different). Restart the
backend if needed to load the memory rule. From Incidents, analyze a selected DAG,
inspect Investigation tabs, then open Copilot or Remediation. Saved work is under
Source Reviews; terminal reviews expose Engineer Feedback in Execution & feedback.
