import { useState } from "react";
import { incidentPath, post } from "./api";
import {
  Panel,
  Badge,
  ErrorState,
  Loading,
  Empty,
  Details,
  Markdown,
} from "./ui";

export function Overview({ catalog, health, reviews, observations, feed }) {
  const records = reviews.data || [];
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Local operations console</p>
          <h1>Operations overview</h1>
          <p>Evidence, engineering decisions and controlled remediation.</p>
        </div>
        <a className="button primary" href="#/incidents">
          Browse incidents
        </a>
      </header>
      <div className="metrics">
        <div>
          <span>Intelligence API</span>
          <Badge>
            {health.error ? "Unavailable" : health.data?.status || "Checking"}
          </Badge>
        </div>
        <div>
          <span>Airflow catalog</span>
          <Badge>
            {catalog.error
              ? "Unavailable"
              : catalog.loading
                ? "Checking"
                : "Connected"}
          </Badge>
        </div>
        <div>
          <span>Registered DAGs</span>
          <strong>
            {catalog.data?.total_registered_dags ??
              catalog.data?.registered_dags?.length ??
              "Unavailable"}
          </strong>
        </div>
        <div>
          <span>Source reviews awaiting approval</span>
          <strong>
            {reviews.data
              ? records.filter((r) => r.state === "validated").length
              : "Unavailable"}
          </strong>
        </div>
      </div>
      <div className="split">
        <Panel title="Recent investigations">
          <p className="muted">
            Analyzed in this session. The catalog does not supply aggregate
            failed-run counts.
          </p>
          {!Object.keys(observations).length ? (
            <Empty title="No investigations yet">
              Open an incident to analyze its latest evidence.
            </Empty>
          ) : (
            <ul className="record-list">
              {Object.values(observations).map((r) => (
                <li key={`${r.type}/${r.id}`}>
                  <a href={`#${incidentPath(r.type, r.id)}`}>{r.id}</a>
                  <Badge>{r.data.incident.class}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Recent source activity">
          <ErrorState message={reviews.error} retry={reviews.refresh} />
          {reviews.loading ? (
            <Loading />
          ) : !records.length ? (
            <Empty title="No persisted source reviews">
              A valid Copilot source proposal creates a review automatically.
            </Empty>
          ) : (
            <ul className="record-list">
              {[...records]
                .reverse()
                .slice(0, 6)
                .map((r) => (
                  <li key={r.proposal_id}>
                    <a href={`#/reviews/${r.proposal_id}`}>{r.dag_id}</a>
                    <Badge>{r.state}</Badge>
                  </li>
                ))}
            </ul>
          )}
        </Panel>
      </div>
      <Panel title="Detection and AI availability">
        <p>
          {feed.data?.new_incident
            ? `New failed run detected: ${feed.data.incident.dag_id}`
            : feed.error
              ? "Incident detection unavailable. Browse and analyze incidents manually."
              : feed.data?.message || "Checking incident detection..."}
        </p>
        {feed.data?.incident && (
          <a href={`#${incidentPath("dag", feed.data.incident.dag_id)}`}>
            Investigate detected failure
          </a>
        )}
        <p className="muted">
          AI availability is reported per analysis or Copilot request. No
          provider-health endpoint is available.
        </p>
      </Panel>
    </>
  );
}

export function Incidents({ catalog, observations }) {
  const [query, setQuery] = useState("");
  const [classification, setClassification] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("asc");
  const rows = [
    ...(catalog.data?.registered_dags || []),
    ...(catalog.data?.import_errors || []),
  ].map((r) => ({ ...r, analysis: observations[`${r.type}/${r.id}`]?.data }));
  const filtered = rows
    .filter(
      (r) =>
        `${r.label} ${r.id}`.toLowerCase().includes(query.toLowerCase()) &&
        (!classification || r.analysis?.incident?.class === classification) &&
        (!status ||
          (r.analysis?.evidence?.latest_dag_run_state || r.status) === status),
    )
    .sort(
      (a, b) =>
        String(a.label).localeCompare(String(b.label)) *
        (sort === "asc" ? 1 : -1),
    );
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Airflow catalog</p>
          <h1>Incidents</h1>
          <p>
            Select a DAG or import error. Run details and classification appear
            after analysis.
          </p>
        </div>
        <button onClick={catalog.refresh}>Refresh catalog</button>
      </header>
      <Panel>
        <div className="toolbar filters">
          <label>
            Search incidents
            <input
              placeholder="Search DAG or import filename"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label>
            Classification
            <select
              value={classification}
              onChange={(e) => setClassification(e.target.value)}
            >
              <option value="">All classifications</option>
              {[
                ...new Set(
                  rows.map((r) => r.analysis?.incident?.class).filter(Boolean),
                ),
              ].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            State
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All states</option>
              {[
                ...new Set(
                  rows.map(
                    (r) =>
                      r.analysis?.evidence?.latest_dag_run_state || r.status,
                  ),
                ),
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Sort
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="asc">DAG A–Z</option>
              <option value="desc">DAG Z–A</option>
            </select>
          </label>
        </div>
        <ErrorState message={catalog.error} retry={catalog.refresh} />
        {catalog.loading ? (
          <Loading>Loading Airflow catalog...</Loading>
        ) : !filtered.length ? (
          <Empty title="No matching incidents">
            Clear filters or refresh the Airflow catalog.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "State",
                    "DAG / import file",
                    "Failed task",
                    "Classification",
                    "Exception",
                    "Human review",
                    "",
                  ].map((h, i) => (
                    <th key={i}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={`${r.type}/${r.id}`}>
                    <td>
                      <Badge>
                        {r.analysis?.evidence?.latest_dag_run_state || r.status}
                      </Badge>
                    </td>
                    <td className="dag-cell">
                      <strong>{r.label}</strong>
                      <small>
                        {r.type === "import_error"
                          ? "Import error"
                          : r.is_paused
                            ? "Paused"
                            : "Registered DAG"}
                      </small>
                    </td>
                    <td>
                      {r.analysis?.evidence?.failed_task_id || "Not analyzed"}
                    </td>
                    <td>{r.analysis?.incident?.class || "Not analyzed"}</td>
                    <td>
                      {r.analysis?.evidence?.failure_exception_type ||
                        "Unavailable"}
                    </td>
                    <td>
                      {r.analysis
                        ? r.analysis.incident.human_review
                          ? "Required"
                          : "Not requested"
                        : "Not analyzed"}
                    </td>
                    <td>
                      <a
                        className="button"
                        href={`#${incidentPath(r.type, r.id)}`}
                      >
                        Open incident
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

export function ManualAnalysis() {
  const [fields, setFields] = useState({
    cpu_usage: "",
    memory_usage: "",
    heartbeat_status: "",
    dag_parse_time: "",
    recent_changes: "",
    scheduler_pod_status: "",
    worker_restarts: "",
  });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(
        await post(
          "/analyze",
          Object.fromEntries(
            Object.entries(fields).map(([k, v]) => [k, Number(v)]),
          ),
        ),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Explicit engineer inputs</p>
          <h1>Manual evidence analysis</h1>
          <p>
            This tool analyzes entered values, not live Airflow observations.
          </p>
        </div>
      </header>
      <Panel>
        <form onSubmit={submit}>
          <div className="form-grid">
            {Object.entries(fields).map(([key, value]) => (
              <label key={key}>
                {key.replaceAll("_", " ")}
                <input
                  type="number"
                  step="any"
                  required
                  value={value}
                  onChange={(e) =>
                    setFields({ ...fields, [key]: e.target.value })
                  }
                />
              </label>
            ))}
          </div>
          <button className="primary" disabled={busy}>
            Analyze Incident
          </button>
          <button
            type="button"
            onClick={() => {
              setFields(
                Object.fromEntries(Object.keys(fields).map((k) => [k, ""])),
              );
              setResult(null);
            }}
          >
            Reset form
          </button>
        </form>
        <ErrorState message={error} />
        {result && (
          <>
            <Details
              data={{
                incident: result.incident,
                SHAP_contributions: result.explanation,
                escalation: result.escalation,
              }}
            />
            <ul>
              {result.guidance?.l1_checks?.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
            <Markdown text={result.guidance?.runbook_content} />
          </>
        )}
      </Panel>
    </>
  );
}
