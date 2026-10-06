import { useEffect, useRef, useState } from "react";
import { post, incidentPath, useResource } from "./api";
import { Badge, ErrorState, Loading, Details } from "./ui";
import Investigation from "./Investigation";
import Copilot from "./Copilot";
import RuntimeRemediation from "./RuntimeRemediation";
import Lifecycle from "./Lifecycle";

export default function IncidentWorkspace({ type, id, tab, onAnalyzed }) {
  const [analysis, setAnalysis] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [proposalId, setProposalId] = useState(null);
  const controller = useRef(null);
  const proposal = useResource(
    proposalId ? `/source-remediations/${proposalId}` : null,
  );
  useEffect(() => () => controller.current?.abort(), []);
  async function analyze() {
    controller.current?.abort();
    controller.current = new AbortController();
    const signal = controller.current.signal;
    setBusy(true);
    setError("");
    try {
      const data = await post(
        type === "dag"
          ? `/analyze-airflow?dag_id=${encodeURIComponent(id)}`
          : `/analyze-import-error?import_error_id=${encodeURIComponent(id)}`,
        undefined,
        signal,
      );
      if (!signal.aborted) {
        setAnalysis(data);
        setProposalId(null);
        onAnalyzed(type, id, data);
      }
    } catch (err) {
      if (!signal.aborted) setError(err.message);
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  }
  const run = analysis?.timeline?.find((event) => event.metadata?.dag_run_id)
    ?.metadata?.dag_run_id;
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">
            {type === "dag"
              ? "Incident workspace / latest run"
              : "DAG import failure"}
          </p>
          <h1 className="identifier">{id}</h1>
        </div>
        <button className="primary" disabled={busy} onClick={analyze}>
          {busy ? "Analyzing..." : "Analyze Live Airflow"}
        </button>
      </header>
      <section className="incident-header">
        <div className="toolbar">
          <Badge>
            {analysis?.evidence?.latest_dag_run_state || "Not analyzed"}
          </Badge>
          <strong>
            {analysis?.incident?.class || "Classification unavailable"}
          </strong>
          <span>{analysis?.incident?.decision_mode?.replaceAll("_", " ")}</span>
          <span>
            {analysis?.incident?.human_review ? "Human review required" : ""}
          </span>
        </div>
        <Details
          data={{
            run: run || "Not supplied",
            failed_task: analysis?.evidence?.failed_task_id,
            exception: analysis?.evidence?.failure_exception_type,
          }}
        />
      </section>
      <Lifecycle analysis={analysis} record={proposal.data} busy={busy} />
      <nav className="tabs" aria-label="Incident workspace">
        {[
          ["investigation", "Investigation"],
          ["copilot", "Developer Copilot"],
          ["remediation", "Remediation"],
        ].map(([path, title]) => (
          <a
            key={path}
            aria-current={tab === path ? "page" : undefined}
            href={`#${incidentPath(type, id, path)}`}
          >
            {title}
          </a>
        ))}
      </nav>
      <ErrorState message={error} retry={analyze} />
      {busy && <Loading>Loading incident evidence and intelligence...</Loading>}
      <div hidden={tab !== "investigation"}>
        <Investigation data={analysis} />
      </div>
      <div hidden={tab !== "copilot"}>
        <Copilot
          key={run || "unanalyzed"}
          type={type}
          id={id}
          analysis={analysis}
          onProposal={setProposalId}
        />
      </div>
      <div hidden={tab !== "remediation"}>
        <RuntimeRemediation
          key={run || "unanalyzed"}
          type={type}
          dagId={id}
          analysis={analysis}
          proposalId={proposalId}
          onReanalyze={analyze}
        />
      </div>
    </>
  );
}
