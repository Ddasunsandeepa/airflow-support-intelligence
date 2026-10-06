import { useEffect, useId, useRef, useState } from "react";

export default function EngineerFeedback({
  actionId,
  resource = "actions",
  eligible = true,
}) {
  return (
    <FeedbackForm
      key={`${resource}/${actionId}`}
      actionId={actionId}
      resource={resource}
      eligible={eligible}
    />
  );
}

function FeedbackForm({ actionId, resource, eligible }) {
  const fieldId = useId();
  const [reload, setReload] = useState(0);
  const [useful, setUseful] = useState("");
  const [quality, setQuality] = useState("");
  const [comment, setComment] = useState("");
  const [saved, setSaved] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const endpoint = `/api/${resource}/${encodeURIComponent(actionId)}/feedback`;

  useEffect(() => {
    const controller = new AbortController();
    fetch(endpoint, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok)
          throw new Error(
            "Could not load saved feedback. Retry loading before submitting to avoid an uncertain duplicate.",
          );
        setSaved(await response.json());
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [endpoint, reload]);

  async function submit(event) {
    event.preventDefault();
    if (
      inFlight.current ||
      saved ||
      !eligible ||
      loading ||
      error ||
      useful === "" ||
      quality === ""
    )
      return;
    inFlight.current = true;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          useful: useful === "true",
          change_quality: quality,
          comment: comment.trim() || null,
        }),
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Feedback could not be saved. Please retry.",
        );
      setSaved(data);
    } catch (err) {
      setError(err.message || "Feedback could not be saved. Please retry.");
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  return (
    <section className="panel feedback-card" aria-labelledby={fieldId}>
      <div className="section-heading">
        <div>
          <p className="card-label">POST-EXECUTION EVALUATION</p>
          <h2 id={fieldId}>Engineer Feedback</h2>
          <p>
            Evaluate this controlled{" "}
            {resource === "actions" ? "runtime recovery" : "source remediation"}
            , including its verification result.
          </p>
        </div>
        <span className="tag">EVALUATION ONLY</span>
      </div>
      <p className="feedback-action">Action: {actionId}</p>
      {loading ? (
        <p role="status">Loading feedback...</p>
      ) : saved ? (
        <div className="success-message" role="status">
          <strong>Feedback saved successfully.</strong>
          <p>
            {saved.useful ? "Useful" : "Not useful"} ·{" "}
            {saved.change_quality.replaceAll("_", " ")}
          </p>
          {saved.comment && <p className="feedback-comment">{saved.comment}</p>}
          <p>Submitted {saved.created_at}</p>
        </div>
      ) : !eligible ? (
        <p>Feedback becomes available after remediation execution completes.</p>
      ) : (
        <form onSubmit={submit}>
          <fieldset disabled={submitting}>
            <legend>Was this remediation useful?</legend>
            <label>
              <input
                type="radio"
                name={fieldId}
                value="true"
                checked={useful === "true"}
                onChange={(e) => setUseful(e.target.value)}
                required
              />{" "}
              Useful
            </label>
            <label>
              <input
                type="radio"
                name={fieldId}
                value="false"
                checked={useful === "false"}
                onChange={(e) => setUseful(e.target.value)}
                required
              />{" "}
              Not Useful
            </label>
          </fieldset>
          <label className="input-group">
            <span>Change quality (required)</span>
            <select
              aria-label="Change quality"
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              required
              disabled={submitting}
            >
              <option value="">Select quality</option>
              <option value="correct">Correct</option>
              <option value="partially_correct">Partially Correct</option>
              <option value="incorrect">Incorrect</option>
            </select>
          </label>
          <label className="input-group">
            <span>Optional comment</span>
            <textarea
              rows={3}
              maxLength={4000}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={submitting}
            />
          </label>
          <p className="muted" role="status">
            {useful === ""
              ? "Select whether this remediation was useful."
              : quality === ""
                ? "Select change quality before submitting."
                : "Ready to submit your evaluation."}
          </p>
          <button
            className="analyze-button"
            type="submit"
            disabled={
              submitting || Boolean(error) || useful === "" || quality === ""
            }
          >
            {submitting ? "Saving Feedback..." : "Submit Feedback"}
          </button>
        </form>
      )}
      {error && !saved && (
        <div className="alert danger" role="alert">
          {error}
          <button
            onClick={() => {
              setError("");
              setLoading(true);
              setReload((n) => n + 1);
            }}
          >
            Retry feedback
          </button>
        </div>
      )}
      <p className="feedback-note">
        Feedback is stored for future evaluation. It does not retrain models,
        modify DAGs, change approval, or execute another action.
      </p>
    </section>
  );
}
