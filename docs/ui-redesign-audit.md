# Console redesign audit

The existing Vite/React application has no router or API abstraction. App.jsx
owns analysis, chat, selection, source review and runtime action state in one
2,000-line component. The catalog does not return per-DAG run/classification
history; those values must remain unavailable until analyzed. No users,
authentication, environment list, aggregate failed-DAG metric or runtime action
list endpoint exists. The UI must not invent these.

| Feature | Old component | Contract | State / issue | New location |
| --- | --- | --- | --- | --- |
| Health/catalog | App | GET /health, /airflow-catalog | Static green API indicator; giant select | Shell, overview, searchable incidents |
| Detection | App | GET /incident-feed | Poll switches selection without clearing action/chat | Non-disruptive incident notice |
| Live analysis/import errors | App | POST /analyze-airflow, /analyze-import-error | Uncancelled requests overwrite a later selection | Incident workspace |
| Manual evidence | App | POST /analyze | Always dominant, defaults resemble live data | Explicit manual-analysis tool |
| Timeline/evidence/SHAP/runbook | App | analysis response | Long vertical report, inferred/observed mixed | Investigation tabs |
| Copilot | App, CopilotInvestigation | POST /developer/chat | Response may attach to newly selected DAG | Incident-scoped Copilot |
| Source review creation | Copilot backend | successful proposal persists immediately | Frontend history does not invalidate | Source Reviews table |
| Source history | SourceRemediationHistory | GET /source-remediations, /{id} | Fetch only mount/DAG/manual refresh; old list flashes on selection | Persisted review routes, automatic revalidation |
| Source review/edit | SourceRemediationWorkspace | PUT /{id}/source; POST reset/validate/approve/reject/execute | Safe contracts, long page; consequential actions lack confirmation | Dedicated tabbed review workspace |
| Runtime actions | App | POST /actions, edit/approve/reject/execute; GET /{id} | Old action survives DAG selection; mode=failure hardcoded for every DAG | Separate operational workspace, explicit JSON config |
| Feedback | EngineerFeedback | GET/POST /actions/{id}/feedback or /source-remediations/{id}/feedback | Silently disabled until usefulness AND quality; endpoint changes do not clear form/saved state | Terminal result/feedback panel with requirements and retry |
| Audit | SourceRemediationWorkspace | persisted audit/revisions | Buried below editor | Audit route + review activity tab |

Feedback POST requires boolean useful and quality enum; comment is optional.
Runtime feedback eligibility is succeeded/failed; source feedback uses its terminal
states. Duplicate submissions are idempotent: first record wins. Existing tests
confirm both endpoints accept valid payloads; no evidence supports bypassing the
required fields or changing backend eligibility. The UI fix explains disabled
states, scopes forms by endpoint, exposes load/retry errors and reloads persistence.

Memory demo was inspected read-only. It raises MemoryError on an estimated
139.42 MB > 64 MB condition, never reads dag_run.conf, and cannot be repaired by
mode=recovery. Configuration's substring `config` matches `configured` before
resource rules; MemoryError is not recognized there. Fix: explicit task MemoryError
after parsing/Kubernetes evidence, before generic configuration text. Suppress a
runtime trigger recommendation for that structured failure; investigate resource
use/source instead. No write-policy expansion.

Implementation choice: retain React/Vite, no new packages. Hash routes provide
back/forward and persisted-review deep links without server rewrite requirements.
A small abortable fetch hook with focus/mutation revalidation separates server
data from incident-local state. Reuse source execution backend and authoritative
diff; use native modal dialogs and semantic controls. No live mutations in QA.
