import { useEffect, useRef, useState } from "react";
import { post, invalidate } from "./api";
import { Panel, Empty, ErrorState, Details, Loading } from "./ui";
import CopilotInvestigation from "./CopilotInvestigation";

export default function Copilot({ type, id, analysis, onProposal }) {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fallback, setFallback] = useState(false);
  const controller = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function send(event) {
    event.preventDefault();
    if (!message.trim() || busy) return;
    const question = message.trim();
    setMessage("");
    setBusy(true);
    setError("");
    controller.current = new AbortController();
    try {
      const result = await post(
        "/developer/chat",
        {
          message: question,
          incident_type: type,
          ...(type === "dag"
            ? { dag_id: id, allow_demo_fallback: fallback }
            : { import_error_id: id }),
        },
        controller.current.signal,
      );
      setMessages((old) => [...old, { question, result }]);
      if (result.code_change?.source_remediation_id) {
        invalidate();
        onProposal(result.code_change.source_remediation_id);
      }
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      if (!controller.current.signal.aborted) setBusy(false);
    }
  }
  return (
    <div className="copilot-layout">
      <Panel title="Developer Copilot">
        <p className="muted">
          Investigate the actual task evidence and source. Proposals require
          engineer review.
        </p>
        <div className="conversation">
          {!messages.length && (
            <Empty title="Start an investigation">
              Ask a focused engineering question about this incident.
            </Empty>
          )}
          {messages.map(({ question, result }, i) => (
            <article className="exchange" key={i}>
              <h3>{question}</h3>
              <p className="eyebrow">Diagnosis</p>
              <p>{result.diagnosis?.summary}</p>
              <h4>Reasoning</h4>
              <p>{result.reasoning}</p>
              <CopilotInvestigation result={result} />
              <h4>Recommended change</h4>
              <p>{result.recommended_fix}</p>
              <p>{result.code_change?.reason}</p>
              {result.code_change?.generated_by?.includes("fallback") && (
                <p className="alert warning">
                  Controlled demo fallback — not AI generated
                </p>
              )}
              <h4>Tests to run</h4>
              <ul>
                {result.tests_to_run?.map((test, n) => (
                  <li key={n}>{test}</li>
                ))}
              </ul>
              {result.code_change?.source_remediation_id && (
                <a
                  className="button primary"
                  href={`#/reviews/${result.code_change.source_remediation_id}`}
                >
                  Review Proposed Change
                </a>
              )}
            </article>
          ))}
        </div>
        {busy && <Loading>Investigating source and evidence...</Loading>}
        <ErrorState message={error} />
        <form onSubmit={send}>
          <label>
            Engineering question
            <textarea
              placeholder="Ask about this DAG failure..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
            />
          </label>
          <div className="toolbar">
            <button className="primary" disabled={busy || !message.trim()}>
              Send
            </button>
            <details>
              <summary>Demo testing options</summary>
              <label className="check">
                <input
                  type="checkbox"
                  checked={fallback}
                  onChange={(e) => setFallback(e.target.checked)}
                />
                Allow labelled demo fallback if AI fails (infrastructure testing
                only)
              </label>
            </details>
          </div>
        </form>
      </Panel>
      <aside>
        <Panel title="Incident context">
          <Details
            data={{
              DAG: id,
              task: analysis?.evidence?.failed_task_id,
              exception: analysis?.evidence?.failure_exception_type,
              classification: analysis?.incident?.class,
            }}
          />
          <p>
            Source and provider availability are checked when you send a
            question.
          </p>
        </Panel>
        <Panel title="Suggested questions">
          <div className="suggestions">
            {[
              "Why did this task fail?",
              "Explain the evidence.",
              "Inspect the failed source.",
              "Investigate this failure and propose a source-code correction.",
              "What should I validate before applying this?",
              "Could this be infrastructure rather than application code?",
            ].map((text) => (
              <button key={text} onClick={() => setMessage(text)}>
                {text}
              </button>
            ))}
          </div>
        </Panel>
      </aside>
    </div>
  );
}
