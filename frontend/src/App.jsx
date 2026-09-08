import { useState } from "react";

const DEFAULT_EVIDENCE = {
  cpu_usage: 94,
  memory_usage: 88,
  heartbeat_status: 0,
  dag_parse_time: 24,
  recent_changes: 12,
  scheduler_pod_status: 1,
  worker_restarts: 2,
};

function App() {
  const [evidence, setEvidence] = useState(DEFAULT_EVIDENCE);
  const [result, setResult] = useState(null);
  const [airflowResult, setAirflowResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [airflowLoading, setAirflowLoading] = useState(false);
  const [error, setError] = useState("");
  const [airflowError, setAirflowError] = useState("");

  const handleChange = (event) => {
    const { name, value } = event.target;

    setEvidence((previous) => ({
      ...previous,
      [name]: Number(value),
    }));
  };

  const analyzeIncident = async () => {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(evidence),
      });

      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }

      const data = await response.json();

      setResult(data);
    } catch (err) {
      setError(
        "Could not connect to the Airflow Support Intelligence API. " +
          "Make sure the FastAPI server is running."
      );
    } finally {
      setLoading(false);
    }
  };

  const analyzeLiveAirflow = async () => {
    setAirflowLoading(true);
    setAirflowError("");
    setAirflowResult(null);

    try {
      const response = await fetch("/api/analyze-airflow", {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(
          `Airflow analysis request failed with status ${response.status}`
        );
      }

      const data = await response.json();

      setAirflowResult(data);
    } catch (err) {
      setAirflowError(
        "Could not analyze the local Airflow environment. " +
          "Make sure the Airflow API and FastAPI server are running."
      );
    } finally {
      setAirflowLoading(false);
    }
  };

  const resetAnalysis = () => {
    setEvidence(DEFAULT_EVIDENCE);
    setResult(null);
    setAirflowResult(null);
    setError("");
    setAirflowError("");
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <p className="eyebrow">AIRFLOW OPERATIONS</p>

          <h1>Airflow Support Intelligence</h1>

          <p className="subtitle">
            AI-assisted L1 incident investigation and support guidance
          </p>
        </div>

        <div className="status-badge">
          <span className="status-dot"></span>
          Intelligence API
        </div>
      </header>

      <main className="dashboard">
        {/* Incident Evidence */}
        <section className="card evidence-card">
          <div className="section-heading">
            <div>
              <h2>Incident Evidence</h2>

              <p>
                Provide the available Airflow and infrastructure evidence.
              </p>
            </div>
          </div>

          <div className="evidence-grid">
            <EvidenceInput
              label="CPU Usage"
              name="cpu_usage"
              value={evidence.cpu_usage}
              suffix="%"
              onChange={handleChange}
            />

            <EvidenceInput
              label="Memory Usage"
              name="memory_usage"
              value={evidence.memory_usage}
              suffix="%"
              onChange={handleChange}
            />

            <EvidenceInput
              label="Heartbeat Status"
              name="heartbeat_status"
              value={evidence.heartbeat_status}
              onChange={handleChange}
            />

            <EvidenceInput
              label="DAG Parse Time"
              name="dag_parse_time"
              value={evidence.dag_parse_time}
              suffix="min"
              onChange={handleChange}
            />

            <EvidenceInput
              label="Recent Changes"
              name="recent_changes"
              value={evidence.recent_changes}
              onChange={handleChange}
            />

            <EvidenceInput
              label="Scheduler Pod Status"
              name="scheduler_pod_status"
              value={evidence.scheduler_pod_status}
              onChange={handleChange}
            />

            <EvidenceInput
              label="Worker Restarts"
              name="worker_restarts"
              value={evidence.worker_restarts}
              onChange={handleChange}
            />
          </div>

          <div className="action-row">
            <button
              className="analyze-button"
              onClick={analyzeIncident}
              disabled={loading}
            >
              {loading ? "Analyzing..." : "Analyze Incident"}
            </button>

            <button
              className="airflow-button"
              onClick={analyzeLiveAirflow}
              disabled={airflowLoading}
            >
              {airflowLoading ? "Analyzing Airflow..." : "Analyze Live Airflow"}
            </button>

            <button className="reset-button" onClick={resetAnalysis}>
              Reset
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}

          {airflowError && (
            <div className="error-message">{airflowError}</div>
          )}
        </section>

        {/* Manual ML Results */}
        {result && (
          <>
            {/* Classification */}
            <section className="result-grid">
              <div className="card classification-card">
                <p className="card-label">INCIDENT CLASSIFICATION</p>

                <div className="classification-content">
                  <div>
                    <h2>{result.incident.class}</h2>

                    <p>Predicted incident type</p>
                  </div>

                  <div className="confidence">
                    <span>
                      {(result.incident.confidence * 100).toFixed(1)}%
                    </span>
                    <small>confidence</small>
                  </div>
                </div>
              </div>

              <div className="card decision-card">
                <p className="card-label">L1 GUIDANCE</p>

                <h3>{result.escalation.recommendation}</h3>

                <p>
                  This is guidance for the support engineer. The system does
                  not automatically modify the production environment.
                </p>
              </div>
            </section>

            {/* Explainability */}
            <section className="card">
              <div className="section-heading">
                <div>
                  <h2>Why did the model predict this?</h2>

                  <p>
                    Top SHAP contributors to the model's classification.
                  </p>
                </div>

                <span className="tag">SHAP</span>
              </div>

              <div className="contributors">
                {result.explanation.top_contributors.map((item) => (
                  <div className="contributor" key={item.feature}>
                    <div className="contributor-info">
                      <strong>{formatFeatureName(item.feature)}</strong>

                      <span>
                        Value: {item.value}{" "}
                        {item.shap_value >= 0
                          ? "· Supports"
                          : "· Pushes away"}
                      </span>
                    </div>

                    <div className="bar-container">
                      <div
                        className="bar"
                        style={{
                          width: `${Math.min(
                            Math.abs(item.shap_value) * 250,
                            100
                          )}%`,
                        }}
                      ></div>
                    </div>

                    <strong className="shap-value">
                      {item.shap_value >= 0 ? "+" : ""}
                      {item.shap_value.toFixed(4)}
                    </strong>
                  </div>
                ))}
              </div>
            </section>

            {/* Guidance */}
            <section className="guidance-grid">
              <div className="card">
                <div className="section-heading">
                  <div>
                    <h2>Runbook</h2>

                    <p>
                      Controlled support knowledge selected by the prediction.
                    </p>
                  </div>
                </div>

                <div className="runbook-name">
                  <span className="file-icon">MD</span>

                  <div>
                    <strong>{result.guidance.runbook}</strong>

                    <span>{result.guidance.runbook_status}</span>
                  </div>
                </div>

                <details className="runbook-details">
                  <summary>View runbook content</summary>

                  <pre>{result.guidance.runbook_content}</pre>
                </details>
              </div>

              <div className="card">
                <div className="section-heading">
                  <div>
                    <h2>L1 Investigation</h2>

                    <p>Recommended diagnostic checks.</p>
                  </div>
                </div>

                <ol className="checks">
                  {result.guidance.l1_checks.map((check, index) => (
                    <li key={index}>
                      <span className="check-number">{index + 1}</span>

                      <span>{check}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </section>

            {/* Safety */}
            <section className="safety-card">
              <div className="safety-icon">!</div>

              <div>
                <strong>Human-in-the-loop support</strong>

                <p>
                  Recommendations assist L1 investigation. Production changes,
                  restarts, resource modifications, and escalation decisions
                  remain under approved operational procedures and engineer
                  judgment.
                </p>
              </div>
            </section>
          </>
        )}

        {/* Live Airflow Results */}
        {airflowResult && (
          <>
            <section className="live-airflow-header">
              <div>
                <p className="card-label">LIVE AIRFLOW ANALYSIS</p>

                <h2>Airflow Operational Evidence</h2>

                <p>
                  Evidence retrieved directly from the connected local
                  Airflow environment.
                </p>
              </div>

              <span
                className={`incident-status ${
                  airflowResult.incident.detected
                    ? "incident-detected"
                    : "no-incident"
                }`}
              >
                {airflowResult.incident.detected
                  ? "Incident Detected"
                  : "No Incident Detected"}
              </span>
            </section>

            <section className="result-grid">
              <div className="card classification-card">
                <p className="card-label">AIRFLOW CLASSIFICATION</p>

                <div className="classification-content">
                  <div>
                    <h2>{airflowResult.incident.class}</h2>

                    <p>{airflowResult.incident.classification_status}</p>
                  </div>

                  <div className="confidence">
                    <span>
                      {airflowResult.incident.classification_confidence ===
                      null
                        ? "—"
                        : `${(
                            airflowResult.incident
                              .classification_confidence * 100
                          ).toFixed(1)}%`}
                    </span>

                    <small>classification confidence</small>
                  </div>
                </div>
              </div>

              <div className="card decision-card">
                <p className="card-label">L1 GUIDANCE / ESCALATION</p>

                <h3>{airflowResult.escalation.recommendation}</h3>

                <p>
                  The system provides investigation guidance only and does not
                  automatically modify the Airflow environment.
                </p>
              </div>
            </section>

            {/* Airflow Evidence */}
            <section className="card">
              <div className="section-heading">
                <div>
                  <h2>Airflow Evidence</h2>

                  <p>
                    Operational signals collected from the Airflow REST API.
                  </p>
                </div>

                <span className="tag">LIVE</span>
              </div>

              <div className="airflow-evidence-grid">
                <EvidenceValue
                  label="Latest DAG Run"
                  value={airflowResult.evidence.latest_dag_run_state}
                />

                <EvidenceValue
                  label="Failed Tasks"
                  value={airflowResult.evidence.failed_task_count}
                />

                <EvidenceValue
                  label="Successful Tasks"
                  value={airflowResult.evidence.successful_task_count}
                />

                <EvidenceValue
                  label="Task Count"
                  value={airflowResult.evidence.task_count}
                />

                <EvidenceValue
                  label="Failed Task"
                  value={airflowResult.evidence.failed_task_id}
                />

                <EvidenceValue
                  label="Operator"
                  value={airflowResult.evidence.failed_task_operator}
                />

                <EvidenceValue
                  label="Exception"
                  value={airflowResult.evidence.failure_exception_type}
                />

                <EvidenceValue
                  label="Scheduler Heartbeat"
                  value={
                    airflowResult.evidence.heartbeat_status === 1
                      ? "Healthy"
                      : "Unhealthy"
                  }
                />

                <EvidenceValue
                  label="DAG Import Errors"
                  value={airflowResult.evidence.dag_import_error_count}
                />

                <EvidenceValue
                  label="DAG Count"
                  value={airflowResult.evidence.dag_count}
                />

                <EvidenceValue
                  label="Failed Task Duration"
                  value={
                    airflowResult.evidence.failed_task_duration !== null
                      ? `${airflowResult.evidence.failed_task_duration.toFixed(
                          3
                        )} s`
                      : "—"
                  }
                />

                <EvidenceValue
                  label="Try Number"
                  value={airflowResult.evidence.failed_task_try_number}
                />
              </div>
            </section>

            {/* Failure Details */}
            <section className="card">
              <div className="section-heading">
                <div>
                  <h2>Failure Details</h2>

                  <p>
                    Error information extracted from the failed Airflow task
                    log.
                  </p>
                </div>
              </div>

              <div className="failure-details">
                <div>
                  <span>Log Event</span>
                  <strong>
                    {airflowResult.evidence.failure_log_event || "—"}
                  </strong>
                </div>

                <div>
                  <span>Exception Type</span>
                  <strong>
                    {airflowResult.evidence.failure_exception_type || "—"}
                  </strong>
                </div>

                <div>
                  <span>Exception Message</span>
                  <strong>
                    {airflowResult.evidence.failure_exception_message || "—"}
                  </strong>
                </div>
              </div>
            </section>

            {/* Live Analysis Reasons */}
            <section className="guidance-grid">
              <div className="card">
                <div className="section-heading">
                  <div>
                    <h2>Evidence Analysis</h2>

                    <p>Reasons supporting the current assessment.</p>
                  </div>
                </div>

                <ul className="checks">
                  {airflowResult.analysis.reasons.map((reason, index) => (
                    <li key={index}>
                      <span className="check-number">{index + 1}</span>

                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="card">
                <div className="section-heading">
                  <div>
                    <h2>L1 Investigation</h2>

                    <p>Recommended diagnostic checks for the support engineer.</p>
                  </div>
                </div>

                <ol className="checks">
                  {airflowResult.guidance.l1_checks.map((check, index) => (
                    <li key={index}>
                      <span className="check-number">{index + 1}</span>

                      <span>{check}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </section>

            {/* Live Runbook */}
            <section className="card">
              <div className="section-heading">
                <div>
                  <h2>Runbook</h2>

                  <p>
                    Controlled support knowledge selected for the current
                    evidence state.
                  </p>
                </div>
              </div>

              <div className="runbook-name">
                <span className="file-icon">MD</span>

                <div>
                  <strong>{airflowResult.guidance.runbook}</strong>

                  <span>{airflowResult.guidance.runbook_status}</span>
                </div>
              </div>

              <details className="runbook-details">
                <summary>View runbook content</summary>

                <pre>{airflowResult.guidance.runbook_content}</pre>
              </details>
            </section>

            {/* Safety */}
            <section className="safety-card">
              <div className="safety-icon">!</div>

              <div>
                <strong>Human-in-the-loop support</strong>

                <p>
                  Live Airflow evidence is used to assist investigation.
                  Root-cause classification remains conservative when the
                  available evidence is insufficient. Production actions and
                  escalation decisions remain under approved operational
                  procedures and engineer judgment.
                </p>
              </div>
            </section>
          </>
        )}

        {!result && !airflowResult && !loading && !airflowLoading && (
          <section className="empty-state">
            <div className="empty-icon">AI</div>

            <h2>Ready to investigate</h2>

            <p>
              Enter incident evidence and select{" "}
              <strong>Analyze Incident</strong>, or connect to local Airflow
              and select <strong>Analyze Live Airflow</strong>.
            </p>
          </section>
        )}
      </main>

      <footer>
        <span>Airflow Support Intelligence</span>

        <span>V1 · AI-assisted L1 support</span>
      </footer>
    </div>
  );
}

function EvidenceInput({
  label,
  name,
  value,
  suffix,
  onChange,
}) {
  return (
    <label className="input-group">
      <span>{label}</span>

      <div className="input-wrapper">
        <input
          type="number"
          name={name}
          value={value}
          onChange={onChange}
        />

        {suffix && <small>{suffix}</small>}
      </div>
    </label>
  );
}

function EvidenceValue({ label, value }) {
  return (
    <div className="evidence-value">
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}

function formatFeatureName(feature) {
  return feature
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default App;