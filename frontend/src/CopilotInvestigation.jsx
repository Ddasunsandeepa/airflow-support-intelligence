export default function CopilotInvestigation({ result }) {
  return (
    <>
      {result.provider_status && (
        <div className="copilot-block">
          <h4>Source investigation provider</h4>
          <p>
            {result.provider_status.replaceAll("_", " ")} ·{" "}
            {result.proposal_status}
          </p>
          {result.provider_attempts?.map((attempt, index) => (
            <p key={index}>
              {attempt.provider} / {attempt.model}: {attempt.status}
              {attempt.http_status ? ` — HTTP ${attempt.http_status}` : ""}
              {attempt.error_category ? ` — ${attempt.error_category}` : ""}
              {attempt.message ? `: ${attempt.message}` : ""}
            </p>
          ))}
        </div>
      )}
      {result.root_cause && (
        <div className="copilot-block">
          <h4>Root Cause (AI inference)</h4>
          <p>{result.root_cause}</p>
        </div>
      )}
      {[
        ["Evidence used by AI", result.evidence_used],
        ["Risks", result.risks],
        ["Assumptions", result.assumptions],
      ].map(
        ([title, items]) =>
          items?.length > 0 && (
            <div className="copilot-block" key={title}>
              <h4>{title}</h4>
              <ul>
                {items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          ),
      )}
      {!result.code_change?.available && result.code_change?.before_code && (
        <details>
          <summary>Current source (read only)</summary>
          <pre className="source-code-block">
            {result.code_change.before_code}
          </pre>
        </details>
      )}
    </>
  );
}
