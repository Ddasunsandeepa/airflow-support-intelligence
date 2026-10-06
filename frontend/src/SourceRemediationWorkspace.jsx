import { useEffect, useRef, useState } from "react";
import UnifiedDiff from "./UnifiedDiff";
import EngineerFeedback from "./EngineerFeedback";
import { Confirm, Tabs, Details, Badge } from "./ui";
import Lifecycle from "./Lifecycle";
import { invalidate, incidentPath } from "./api";

const REVIEWABLE = [
  "proposed",
  "edited",
  "validated",
  "validation_failed",
  "approved",
  "rejected",
];
const TERMINAL = [
  "succeeded",
  "stale_source",
  "apply_failed",
  "apply_failed_rolled_back",
  "airflow_parse_failed",
  "execution_failed",
  "verification_failed",
];

export default function SourceRemediationWorkspace({ proposalId }) {
  const [tab, setTab] = useState("Source & diff");
  const [confirmation, setConfirmation] = useState(null);
  const [reload, setReload] = useState(0);
  const [copyStatus, setCopyStatus] = useState("");
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [role, setRole] = useState("L2");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const endpoint = `/api/source-remediations/${encodeURIComponent(proposalId)}`;

  useEffect(() => {
    const controller = new AbortController();
    fetch(endpoint, { signal: controller.signal })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok)
          throw new Error(data.detail || "Could not load source review.");
        setRecord(data);
        setDraft(data.change.source_code.proposed_code);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });
    return () => controller.abort();
  }, [endpoint, reload]);

  // Execution can span several Airflow parse intervals. Show persisted progress while it runs.
  useEffect(() => {
    if (
      !record ||
      (!busy &&
        (REVIEWABLE.includes(record.state) || TERMINAL.includes(record.state)))
    )
      return;
    const timer = setInterval(() => {
      fetch(endpoint)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data)
            setRecord((current) =>
              data.revision >= current.revision &&
              data.audit.length >= current.audit.length
                ? data
                : current,
            );
        })
        .catch(() =>
          setError(
            "Execution progress could not be refreshed. Reload the saved review before taking another action.",
          ),
        );
    }, 2000);
    return () => clearInterval(timer);
  }, [endpoint, record, busy]);

  async function request(suffix, data, method = "POST") {
    const response = await fetch(`${endpoint}/${suffix}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const result = await response.json();
    if (!response.ok)
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "Source review request failed.",
      );
    invalidate();
    setRecord(result);
    setDraft(result.change.source_code.proposed_code);
    return result;
  }

  const version = (r) => ({
    revision: r.revision,
    source_hash: r.proposal_hash,
  });
  const dirty = record && draft !== record.change.source_code.proposed_code;
  async function act(action) {
    if (inFlight.current || !record) return;
    setConfirmation(null);
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      let current = record;
      if (action === "save" || (action === "validate" && dirty)) {
        current = await request(
          "source",
          {
            ...version(current),
            proposed_source: draft,
            edited_by: reviewer.trim() || "engineer",
          },
          "PUT",
        );
      }
      if (action !== "save") {
        await request(action, {
          ...version(current),
          ...(action === "approve"
            ? { approved_by: reviewer.trim(), approver_role: role }
            : {}),
        });
      }
    } catch (err) {
      setError(
        `${err.message} Reload the saved review if its state may have changed.`,
      );
      // Preserve unsaved text; reconcile persisted execution status after network errors.
      if (action === "execute") {
        try {
          const response = await fetch(endpoint);
          if (response.ok) setRecord(await response.json());
        } catch {
          /* The explicit reload button remains available. */
        }
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  if (!record)
    return (
      <section className="panel">
        <p role={error ? "alert" : "status"}>
          {error || "Loading source remediation..."}
        </p>
        {error && (
          <button onClick={() => setReload((n) => n + 1)}>Retry</button>
        )}
      </section>
    );
  const editable = REVIEWABLE.includes(record.state) && !busy;
  const source = record.change.source_code;
  return (
    <section
      className="panel source-remediation-workspace"
      aria-label="Source Remediation Workspace"
    >
      <div className="section-heading">
        <div>
          <p className="card-label">AI-ASSISTED SOURCE REMEDIATION</p>
          <h2>Source Remediation Workspace</h2>
          <p>{record.dag_id}</p>
        </div>
        <span className="tag">{record.state.replaceAll("_", " ")}</span>
      </div>
      {TERMINAL.includes(record.state) && (
        <div className="alert" role="note">
          <div>
            <strong>Saved result from a previous remediation</strong>
            <p>
              This review keeps its original result when the DAG runs again.
              To investigate a new failure, open the incident, click Analyze
              Live Airflow, then ask Developer Copilot for a new proposal.
            </p>
            <p>
              Review created: {record.created_at}. Corrected run: {record.dag_run_id || "Not created"}.
            </p>
            <a className="button primary" href={`#${incidentPath("dag", record.dag_id)}`}>
              Start a new investigation
            </a>
          </div>
        </div>
      )}
      <p>
        Generated by:{" "}
        <strong>
          {source.generated_by === "developer_llm"
            ? "Developer LLM"
            : "Controlled demo fallback (not AI generated)"}
        </strong>
      </p>
      <p>
        <code>{source.file_path}</code>
      </p>
      <div className="toolbar">
        <Badge>
          {record.validation?.valid && !dirty
            ? "Validated"
            : "Validation required"}
        </Badge>
        <Badge>
          {record.approval && !dirty ? "Approved" : "Human approval required"}
        </Badge>
        <span>Target: {record.target_function}</span>
      </div>
      <Lifecycle
        record={
          dirty ? { ...record, validation: null, approval: null } : record
        }
      />
      <Tabs
        items={[
          "Source & diff",
          "Diagnosis",
          "Validation & approval",
          "Execution & feedback",
          "Audit",
        ]}
        value={tab}
        onChange={setTab}
      />
      {tab === "Diagnosis" && (
        <Details
          data={{ ...record.investigation, tests_to_run: record.tests_to_run }}
        />
      )}
      <div hidden={tab !== "Source & diff"}>
        {!record.execution_allowed && (
          <p>
            Review and editing are available. Source execution is blocked:
            {" "}{record.execution_block_reason || "The source does not meet the execution policy."}
          </p>
        )}
        <details>
          <summary>Observed failure</summary>
          <p>
            {record.evidence.airflow_evidence?.failure_exception_message ||
              "See incident evidence and timeline."}
          </p>
        </details>
        <p>
          Revision {record.revision} ·{" "}
          {dirty
            ? "Unsaved edits — approval and execution disabled until saved, validated and approved."
            : "Saved reviewed source"}
        </p>
        <details>
          <summary>SHA-256: {record.proposal_hash.slice(0, 12)}...</summary>
          <code>{record.proposal_hash}</code>
          <button
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(record.proposal_hash);
                setCopyStatus("Hash copied");
              } catch {
                setCopyStatus("Copy unavailable; select the hash above.");
              }
            }}
          >
            Copy hash
          </button>
          <span role="status">{copyStatus}</span>
        </details>
        <div className="source-code-grid">
          <div>
            <h3>Current source at proposal creation</h3>
            <pre className="source-code-block">{source.before_code}</pre>
          </div>
          <label>
            <h3>Proposed source</h3>
            <textarea
              aria-label="Proposed source"
              spellCheck={false}
              value={draft}
              disabled={!editable}
              onChange={(event) => setDraft(event.target.value)}
              style={{
                width: "100%",
                minHeight: "480px",
                fontFamily: "monospace",
                whiteSpace: "pre",
                boxSizing: "border-box",
              }}
            />
          </label>
        </div>
        <div className="action-buttons">
          <button disabled={!editable} onClick={() => act("reset")}>
            Reset to{" "}
            {source.generated_by === "developer_llm" ? "AI" : "Original"}{" "}
            Proposal
          </button>
          <button disabled={!editable || !dirty} onClick={() => act("save")}>
            Save Reviewed Version
          </button>
          <button disabled={!editable} onClick={() => act("validate")}>
            Validate Changes
          </button>
        </div>
        <h3>Exact change (saved revision)</h3>
        <p>
          +{record.change.additions} −{record.change.deletions}
        </p>
        {dirty && (
          <p>
            The diff below represents the saved version. Save or validate to
            recalculate it.
          </p>
        )}
        <UnifiedDiff diff={record.change.unified_diff} />
      </div>
      <div hidden={tab !== "Validation & approval"}>
        {dirty && (
          <p className="alert warning">
            Unsaved changes: validation and approval are stale. Save or validate
            the edited source first.
          </p>
        )}
        <button disabled={!editable} onClick={() => act("validate")}>
          Validate reviewed revision
        </button>
        <h3>Validation</h3>
        {record.validation && !dirty ? (
          <ul>
            {Object.entries(record.validation.checks).map(([name, passed]) => (
              <li key={name}>
                {name.replaceAll("_", " ")}: {passed ? "Passed" : "Failed"}
              </li>
            ))}
          </ul>
        ) : (
          <p>Validation required for this reviewed version.</p>
        )}
        {record.validation?.errors.map((message) => (
          <p className="error-message" key={message}>
            {message}
          </p>
        ))}
        <p>
          Airflow parse check:{" "}
          {record.airflow_parse?.status || "Pending explicit execution"}
        </p>
        <h3>Human approval</h3>
        <p style={{ overflowWrap: "anywhere" }}>
          Reviewed SHA-256: <code>{record.proposal_hash}</code>
        </p>
        <label>
          Reviewer name{" "}
          <input
            aria-label="Reviewer name"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            disabled={!editable}
          />
        </label>
        <label>
          Reviewer role{" "}
          <select
            aria-label="Reviewer role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            disabled={!editable}
          >
            <option>L2</option>
            <option>ADMIN</option>
          </select>
        </label>
        <p>
          Local PoC: reviewer identity/role is self-declared; use only in your
          trusted local environment.
        </p>
        {record.approval && !dirty && (
          <p>
            Approved by {record.approval.approved_by}: revision{" "}
            {record.approval.revision}.
          </p>
        )}
        <div className="action-buttons">
          <button
            disabled={!editable || dirty}
            onClick={() => setConfirmation("reject")}
          >
            Reject
          </button>
          <button
            disabled={
              !record.execution_allowed ||
              !editable ||
              dirty ||
              record.state !== "validated" ||
              !reviewer.trim()
            }
            onClick={() => setConfirmation("approve")}
          >
            Approve Reviewed Change
          </button>
        </div>
      </div>
      {busy && <p role="status">Processing source remediation...</p>}
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {error && (
        <button
          disabled={busy}
          onClick={async () => {
            try {
              const response = await fetch(endpoint);
              if (!response.ok)
                throw new Error("Could not reload the saved review.");
              const saved = await response.json();
              setRecord(saved);
              setDraft(saved.change.source_code.proposed_code);
              setError("");
            } catch (err) {
              setError(err.message);
            }
          }}
        >
          Reload saved review (discard unsaved edits)
        </button>
      )}
      <div hidden={tab !== "Execution & feedback"} className="execution">
        <h3>Controlled execution</h3>
        <p>
          Apply revision {record.revision} to {record.dag_id}, after an
          original-source backup. Wait for Airflow recognition, then trigger
          with empty configuration and verify.
        </p>
        <button
          className="danger-button"
          disabled={
            !record.execution_allowed ||
            busy ||
            dirty ||
            record.state !== "approved"
          }
          onClick={() => setConfirmation("execute")}
        >
          Execute Approved Remediation
        </button>
        {record.state !== "approved" && (
          <p>
            Exact-version validation and approval are required before execution.
          </p>
        )}
        <h3>Execution and verification</h3>
        <p>
          Source applied: {record.applied_at || "Pending"}
          {record.state === "apply_failed_rolled_back" ? " (rolled back)" : ""}
        </p>
        <p>Corrected DAG run: {record.dag_run_id || "Pending"}</p>
        <p>Verification: {record.verification?.status || "Pending"}</p>
        {record.verification && (
          <pre>{JSON.stringify(record.verification, null, 2)}</pre>
        )}
        <p>Backup: {record.backup_path || "Not created"}</p>
        <EngineerFeedback
          key={record.proposal_id}
          actionId={record.proposal_id}
          resource="source-remediations"
          eligible={TERMINAL.includes(record.state)}
        />
      </div>
      <div hidden={tab !== "Audit"}>
        <details open>
          <summary>Audit trail</summary>
          <ol>
            {record.audit.map((event, i) => (
              <li key={i}>
                {event.created_at} — revision {event.revision} — {event.state}:{" "}
                {event.message}
              </li>
            ))}
          </ol>
        </details>
        <details>
          <summary>Original proposal and revision history</summary>
          {record.revisions.map((revision) => (
            <div key={revision.revision}>
              <h4>
                Revision {revision.revision} — {revision.edited_by}
              </h4>
              <pre className="source-code-block">{revision.source}</pre>
            </div>
          ))}
        </details>
      </div>
      {confirmation && (
        <Confirm
          title={`${confirmation} reviewed change`}
          onCancel={() => setConfirmation(null)}
          onConfirm={() => act(confirmation)}
        >
          <Details
            data={{
              DAG: record.dag_id,
              revision: record.revision,
              SHA256: record.proposal_hash,
              reviewer,
              role,
            }}
          />
          <p>
            {confirmation === "execute"
              ? "This will back up and write the exact approved source, wait for Airflow parsing and trigger a corrected run."
              : "Your decision applies only to this exact saved revision and hash."}
          </p>
        </Confirm>
      )}
    </section>
  );
}
