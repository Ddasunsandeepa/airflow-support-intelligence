import { useState } from "react";
import { Panel, Tabs, Details, Empty, Markdown, Badge } from "./ui";

export default function Investigation({ data }) {
  const [tab, setTab] = useState("Summary");
  if (!data)
    return (
      <Empty title="Ready to investigate">
        Analyze the selected incident to retrieve current Airflow evidence.
        Analysis does not trigger a DAG.
      </Empty>
    );
  const checks = data.guidance?.l1_checks || [];
  return (
    <>
      <Tabs
        items={["Summary", "Timeline", "Evidence", "Intelligence", "Runbook"]}
        value={tab}
        onChange={setTab}
      />
      {tab === "Summary" && (
        <div className="split">
          <Panel title="Failure summary">
            <p className="eyebrow">Observed in Airflow</p>
            <h3>
              {data.evidence?.failure_exception_type ||
                data.incident?.class ||
                "No exception reported"}
            </h3>
            <p className="failure-message">
              {data.evidence?.failure_exception_message ||
                "No task exception is available."}
            </p>
            <Details
              data={{
                failed_task: data.evidence?.failed_task_id,
                operator: data.evidence?.failed_task_operator,
                run_state: data.evidence?.latest_dag_run_state,
              }}
            />
            <h3>Supporting evidence</h3>
            <ul>
              {data.evidence_signals?.supporting_evidence?.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </Panel>
          <Panel title="Recommended investigation">
            <p className="eyebrow">Interpretation and next steps</p>
            <ol>
              {checks.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
            <Details data={data.escalation} />
          </Panel>
        </div>
      )}
      {tab === "Timeline" && (
        <Panel title="Incident timeline">
          {!data.timeline?.length ? (
            <Empty title="No timeline events">
              Timestamps have not been supplied for this incident.
            </Empty>
          ) : (
            <ol className="timeline">
              {data.timeline.map((event, i) => (
                <li key={i}>
                  <time>{event.timestamp || "Time unavailable"}</time>
                  <div>
                    <h3>
                      {event.title} <Badge>{event.severity}</Badge>
                    </h3>
                    <p>{event.description}</p>
                    <small>{event.source}</small>
                    <details>
                      <summary>Event details</summary>
                      <Details data={event.metadata} />
                    </details>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      )}
      {tab === "Evidence" && (
        <div className="split">
          <Panel title="Airflow evidence">
            <p className="eyebrow">Observed</p>
            <Details data={data.evidence} />
          </Panel>
          <Panel title="Infrastructure evidence">
            {data.kubernetes ? (
              <Details data={data.kubernetes} />
            ) : (
              <Empty title="No Kubernetes evidence">
                No Kubernetes telemetry was supplied for this incident.
              </Empty>
            )}
          </Panel>
        </div>
      )}
      {tab === "Intelligence" && (
        <>
          <Panel title="Hybrid decision">
            <p className="eyebrow">Interpretation</p>
            <Details data={data.incident} />
          </Panel>
          <div className="intelligence-grid">
            {[
              ["ML", data.ml],
              ["Evidence signals", data.evidence_signals],
              ["LLM", data.llm],
            ].map(([title, result]) => (
              <Panel key={title} title={title}>
                <Badge>
                  {result?.status || result?.incident_class || "Unavailable"}
                </Badge>
                <h3>
                  {result?.incident_class || result?.prediction || "Unknown"}
                </h3>
                <p>
                  {title === "Evidence signals"
                    ? "Rule strength, not causal probability"
                    : "Reported confidence"}
                  : {result?.confidence ?? "Unavailable"}
                </p>
                <p>{result?.reasoning}</p>
                <details>
                  <summary>
                    {title === "ML"
                      ? "Model details and SHAP contributions"
                      : "Analysis details"}
                  </summary>
                  <Details data={result} />
                </details>
              </Panel>
            ))}
          </div>
        </>
      )}
      {tab === "Runbook" && (
        <Panel title={data.guidance?.runbook || "Runbook"}>
          {data.guidance?.runbook_content ? (
            <Markdown text={data.guidance.runbook_content} />
          ) : (
            <Empty title="No runbook available">
              {data.guidance?.runbook_status || "Analyze the incident first."}
            </Empty>
          )}
        </Panel>
      )}
    </>
  );
}
