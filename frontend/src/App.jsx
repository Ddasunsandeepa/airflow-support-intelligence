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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

  const resetAnalysis = () => {
    setEvidence(DEFAULT_EVIDENCE);
    setResult(null);
    setError("");
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

            <button className="reset-button" onClick={resetAnalysis}>
              Reset
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}
        </section>

        {/* Results */}
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
                    <span>{(result.incident.confidence * 100).toFixed(1)}%</span>
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
                        {item.shap_value >= 0 ? "· Supports" : "· Pushes away"}
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

                    <p>Controlled support knowledge selected by the prediction.</p>
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

        {!result && !loading && (
          <section className="empty-state">
            <div className="empty-icon">AI</div>

            <h2>Ready to investigate</h2>

            <p>
              Enter incident evidence above and select{" "}
              <strong>Analyze Incident</strong> to run the intelligence
              pipeline.
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

function formatFeatureName(feature) {
  return feature
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default App;