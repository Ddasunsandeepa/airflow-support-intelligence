import { useEffect, useRef, useState } from "react";
import { api, post } from "./api";
import { Panel, Empty, ErrorState, Badge, Confirm, Details } from "./ui";
import UnifiedDiff from "./UnifiedDiff";
import EngineerFeedback from "./EngineerFeedback";

export default function RuntimeRemediation({
  type,
  dagId,
  analysis,
  proposalId,
  onReanalyze,
}) {
  const [action, setAction] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [config, setConfig] = useState("{}");
  const [reason, setReason] = useState("Engineer-reviewed operational action");
  const [confirm, setConfirm] = useState(null);
  const [lookup, setLookup] = useState("");
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  async function operate(operation) {
    if (busy) return;
    setBusy(true);
    setError("");
    setConfirm(null);
    try {
      let data;
      if (operation === "load") {
        data = await api(`/actions/${encodeURIComponent(lookup.trim())}`);
        if (data.request?.dag_id !== dagId)
          throw new Error(
            "This action belongs to another DAG. Open its incident to continue.",
          );
      } else if (operation === "create" || operation === "edit") {
        const conf = JSON.parse(config);
        if (!conf || typeof conf !== "object" || Array.isArray(conf))
          throw new Error("Configuration must be a JSON object.");
        data = await post(
          operation === "create"
            ? "/actions"
            : `/actions/${action.action_id}/edit`,
          operation === "create"
            ? {
                action_type: analysis.remediation_recommendation.action_type,
                dag_id: dagId,
                parameters: { conf },
                reason,
                source: "human_review",
              }
            : { parameters: { conf }, reason },
        );
      } else data = await post(`/actions/${action.action_id}/${operation}`);
      if (!alive.current) return;
      setAction(data.action || data);
      setResult(data.result || null);
      if (["load", "create", "edit"].includes(operation)) {
        setConfig(
          JSON.stringify(
            data.request.parameters.conf ?? data.request.parameters,
            null,
            2,
          ),
        );
        setReason(data.request.reason);
      }
    } catch (err) {
      if (!alive.current) return;
      setError(err.message);
      if (operation === "execute" && action) {
        try {
          const fresh = await api(`/actions/${action.action_id}`);
          if (alive.current) setAction(fresh);
        } catch {
          /* Original error remains visible. */
        }
      }
    } finally {
      if (alive.current) setBusy(false);
    }
  }
  const available =
    type === "dag" && analysis?.remediation_recommendation?.available;
  let dirty = false;
  if (action) {
    try {
      dirty =
        JSON.stringify(JSON.parse(config)) !==
          JSON.stringify(
            action.request.parameters.conf ?? action.request.parameters,
          ) || reason !== action.request.reason;
    } catch {
      dirty = true;
    }
  }
  const terminal = ["succeeded", "failed"].includes(action?.status);
  return (
    <>
      <div className="split">
        <Panel title="Source remediation">
          {proposalId ? (
            <a className="button primary" href={`#/reviews/${proposalId}`}>
              Review Proposed Change
            </a>
          ) : (
            <Empty title="Investigate before changing source">
              Ask Developer Copilot to inspect the failed task. Valid proposals
              are saved automatically in Source Reviews.
            </Empty>
          )}
          <a href={`#/reviews?dag=${encodeURIComponent(dagId)}`}>
            Browse source reviews for this DAG
          </a>
        </Panel>
        <Panel title="Operational remediation">
          <p>
            Runtime actions change Airflow execution or configuration, not
            Python source.
          </p>
          {!available ? (
            <Empty title="No operational remediation recommended">
              {analysis?.remediation_recommendation?.reason ||
                "Analyze this incident first."}
            </Empty>
          ) : (
            <>
              <p>{analysis.remediation_recommendation.reason}</p>
              <label>
                Configuration JSON
                <textarea
                  aria-label="Configuration JSON"
                  value={config}
                  onChange={(e) => setConfig(e.target.value)}
                  rows={4}
                  disabled={busy}
                />
              </label>
              <p className="muted">
                Use only configuration supported by this DAG. No recovery mode
                is assumed.
              </p>
              <label>
                Action reason
                <input
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              {!action ? (
                <button
                  disabled={busy || !reason.trim()}
                  onClick={() => operate("create")}
                >
                  Create Remediation Action
                </button>
              ) : (
                !terminal &&
                action.status !== "executing" && (
                  <button disabled={busy} onClick={() => operate("edit")}>
                    Save Changes
                  </button>
                )
              )}
            </>
          )}
          {type === "dag" && (
            <details>
              <summary>Reopen a persisted runtime action</summary>
              <label>
                Action ID
                <input
                  value={lookup}
                  onChange={(e) => setLookup(e.target.value)}
                />
              </label>
              <button
                disabled={busy || !lookup.trim()}
                onClick={() => operate("load")}
              >
                Load action
              </button>
            </details>
          )}
        </Panel>
      </div>
      <ErrorState message={error} />
      {action && (
        <Panel title="Runtime action review">
          <Badge>{action.status}</Badge>
          <Details
            data={{
              action_id: action.action_id,
              DAG: action.request.dag_id,
              action: action.request.action_type,
              parameters: action.request.parameters,
              validation: action.validation,
              approval: action.approval,
            }}
          />
          {action.change_proposal && (
            <>
              <h3>Runtime Configuration Change</h3>
              <UnifiedDiff diff={action.change_proposal.unified_diff} />
            </>
          )}
          <div className="toolbar">
            <button
              disabled={
                busy ||
                dirty ||
                terminal ||
                !["pending_approval", "validated"].includes(action.status)
              }
              onClick={() => setConfirm("approve")}
            >
              Approve Action
            </button>
            <button
              disabled={busy || terminal}
              onClick={() => setConfirm("reject")}
            >
              Reject Action
            </button>
          </div>
          <section className="execution">
            {dirty && (
              <p className="alert warning">
                Unsaved configuration: save and approve the updated action
                before execution.
              </p>
            )}
            <h3>Controlled execution</h3>
            <p>
              Submits the reviewed operational action to {dagId}. This does not
              apply source code.
            </p>
            <button
              className="danger-button"
              disabled={busy || dirty || action.status !== "approved"}
              onClick={() => setConfirm("execute")}
            >
              Execute Approved Action
            </button>
            {busy && (
              <p role="status">
                Request in progress. Execution may wait for Airflow
                verification.
              </p>
            )}
            {result && <Details data={result} />}
            {terminal && !result && (
              <p>
                Persisted action status: {action.status}. Detailed runtime
                execution results are not persisted by this API.
              </p>
            )}
            {terminal && (
              <button onClick={onReanalyze}>Re-analyze latest evidence</button>
            )}
          </section>
          <EngineerFeedback
            key={action.action_id}
            actionId={action.action_id}
            eligible={terminal}
          />
        </Panel>
      )}
      {confirm && (
        <Confirm
          title={`${confirm} action`}
          onCancel={() => setConfirm(null)}
          onConfirm={() => operate(confirm)}
        >
          <Details
            data={{
              action: action.action_id,
              DAG: action.request.dag_id,
              parameters: action.request.parameters,
            }}
          />
          <p>Confirm this exact operational request.</p>
        </Confirm>
      )}
    </>
  );
}
