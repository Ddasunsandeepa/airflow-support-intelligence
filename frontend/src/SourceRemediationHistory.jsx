import { useState } from "react";
import { useResource } from "./api";
import { Badge, Empty, ErrorState, Loading, Panel } from "./ui";

export default function SourceRemediationHistory({
  dagId = "",
  audit = false,
}) {
  const { data, loading, error, refresh } = useResource(
    "/source-remediations",
    15000,
  );
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const records = (data || [])
    .filter(
      (record) =>
        (!dagId || record.dag_id === dagId) &&
        `${record.dag_id} ${record.target_function} ${record.proposal_id}`
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (!state || record.state === state),
    )
    .sort((a, b) =>
      (b.audit.at(-1)?.created_at || b.created_at).localeCompare(
        a.audit.at(-1)?.created_at || a.created_at,
      ),
    );
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Persisted backend records</p>
          <h1>{audit ? "Audit & feedback" : "Source Reviews"}</h1>
          <p>{dagId || "All source investigations"}</p>
        </div>
        <button onClick={refresh}>Refresh</button>
      </header>
      <Panel>
        <p>
          Valid Copilot proposals are saved automatically. Saving reviewed
          source updates the existing proposal and its revision. Completed
          reviews remain available as history; a new failed DAG run needs a new
          investigation and proposal from the Incidents workspace.
        </p>
        <div className="toolbar">
          <label>
            Search reviews
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="DAG, function or proposal ID"
            />
          </label>
          <label>
            Review state
            <select value={state} onChange={(e) => setState(e.target.value)}>
              <option value="">All states</option>
              {[...new Set((data || []).map((r) => r.state))].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          {dagId && <a href="#/reviews">Show all DAGs</a>}
        </div>
        <ErrorState message={error} retry={refresh} />
        {loading ? (
          <Loading />
        ) : !records.length ? (
          <Empty title="No source reviews for this selection">
            When Copilot creates a valid source proposal, it appears here for
            review. Try clearing filters or open Developer Copilot.
          </Empty>
        ) : audit ? (
          <ol className="timeline">
            {records.flatMap((r) =>
              r.audit.map((event, i) => (
                <li key={`${r.proposal_id}/${i}`}>
                  <time>{event.created_at}</time>
                  <div>
                    <h3>{event.state.replaceAll("_", " ")}</h3>
                    <p>{event.message}</p>
                    <a href={`#/reviews/${r.proposal_id}`}>
                      {r.dag_id} / revision {event.revision}
                    </a>
                    {r.feedback_id && (
                      <small>Feedback record: {r.feedback_id}</small>
                    )}
                  </div>
                </li>
              )),
            )}
          </ol>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "Status",
                    "DAG / target",
                    "Revision",
                    "Provenance",
                    "Validation",
                    "Approval",
                    "Updated",
                    "Action",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.proposal_id}>
                    <td>
                      <Badge>{r.state}</Badge>
                    </td>
                    <td className="dag-cell">
                      <strong>{r.dag_id}</strong>
                      <small>{r.target_function}</small>
                    </td>
                    <td>{r.revision}</td>
                    <td>
                      {r.change.source_code.generated_by === "developer_llm"
                        ? "Developer LLM"
                        : "Controlled demo fallback"}
                    </td>
                    <td>
                      {r.validation
                        ? r.validation.valid
                          ? "Passed"
                          : "Failed"
                        : "Required"}
                    </td>
                    <td>
                      {r.approval
                        ? `${r.approval.approved_by} / r${r.approval.revision}`
                        : "Not approved"}
                    </td>
                    <td>
                      <time>{r.audit.at(-1)?.created_at || r.created_at}</time>
                    </td>
                    <td>
                      <a className="button" href={`#/reviews/${r.proposal_id}`}>
                        {[
                          "succeeded",
                          "verification_failed",
                          "execution_failed",
                          "apply_failed_rolled_back",
                        ].includes(r.state)
                          ? "View Result"
                          : "Continue Review"}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
