export default function Lifecycle({ analysis, record, busy }) {
  const labels = [
    "Detected",
    "Analyzed",
    "Proposed",
    "Reviewed",
    "Validated",
    "Approved",
    "Executed",
    "Verified",
  ];
  const completed = [
    Boolean(
      analysis?.incident?.detected ||
        record?.evidence?.airflow_evidence?.failed_task_id,
    ),
    Boolean(analysis || record?.evidence?.hybrid_analysis),
    Boolean(record),
    record?.revision > 1,
    Boolean(
      record?.validation?.valid &&
        record.validation.revision === record.revision &&
        record.validation.source_hash === record.proposal_hash,
    ),
    Boolean(
      record?.approval &&
        record.approval.revision === record.revision &&
        record.approval.source_hash === record.proposal_hash,
    ),
    Boolean(record?.applied_at || record?.dag_run_id),
    record?.state === "succeeded" &&
      record?.verification?.status === "verified",
  ];
  const stage = completed.lastIndexOf(true);
  return (
    <div className="lifecycle" aria-label="Incident lifecycle">
      <ol>
        {labels.map((label, index) => (
          <li
            key={label}
            className={completed[index] ? "complete" : ""}
            aria-label={`${label}: ${completed[index] ? "recorded" : "not recorded"}`}
            aria-current={index === stage ? "step" : undefined}
          >
            <span>{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      {busy && <span role="status">Investigating...</span>}
      {record && /failed|stale|rejected/.test(record.state) && (
        <p role="status" className="text-danger">
          {record.state.replaceAll("_", " ")} — inspect validation and audit
          before continuing.
        </p>
      )}
    </div>
  );
}
