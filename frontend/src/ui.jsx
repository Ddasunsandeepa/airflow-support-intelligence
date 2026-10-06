import { useEffect, useId, useRef } from "react";

export function Badge({ children }) {
  const text = String(children ?? "Unavailable");
  const tone = /failed|error|stale|rolled.back/i.test(text)
    ? "danger"
    : /success|verified|healthy|validated/i.test(text)
      ? "success"
      : /pending|review|proposed|edited|approval/i.test(text)
        ? "warning"
        : "neutral";
  return <span className={`badge ${tone}`}>{text.replaceAll("_", " ")}</span>;
}
export function Panel({ title, children, action, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-heading">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Empty({ title, children }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function ErrorState({ message, retry }) {
  return (
    message && (
      <div role="alert" className="alert danger">
        <span>{message}</span>
        {retry && <button onClick={retry}>Retry</button>}
      </div>
    )
  );
}
export function Loading({ children = "Loading records..." }) {
  return (
    <p className="loading" role="status">
      {children}
    </p>
  );
}
export function Details({ data }) {
  return (
    <dl className="definitions">
      {Object.entries(data || {}).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>
            {value == null ? (
              "Unavailable"
            ) : typeof value === "object" ? (
              <pre>{JSON.stringify(value, null, 2)}</pre>
            ) : (
              String(value)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function Tabs({ items, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item, index) => (
        <button
          key={item}
          role="tab"
          aria-selected={value === item}
          tabIndex={value === item ? 0 : -1}
          onKeyDown={(event) => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
              return;
            event.preventDefault();
            const next =
              event.key === "Home"
                ? 0
                : event.key === "End"
                  ? items.length - 1
                  : (index +
                      (event.key === "ArrowRight" ? 1 : -1) +
                      items.length) %
                    items.length;
            onChange(items[next]);
            event.currentTarget.parentElement.children[next].focus();
          }}
          onClick={() => onChange(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}
export function Confirm({ title, children, onConfirm, onCancel }) {
  const ref = useRef(null);
  const id = useId();
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog ref={ref} aria-labelledby={id} onCancel={onCancel}>
      <h2 id={id}>{title}</h2>
      <div className="dialog-body">{children}</div>
      <div className="toolbar">
        <button autoFocus onClick={onCancel}>
          Cancel
        </button>
        <button className="primary" onClick={onConfirm}>
          Confirm {title.toLowerCase()}
        </button>
      </div>
    </dialog>
  );
}
export function Markdown({ text = "" }) {
  // Render only a safe subset; never inject HTML from runbooks or providers.
  const lines = String(text || "").split("\n");
  return (
    <div className="markdown">
      {lines.map((line, i) => {
        if (line.startsWith("```")) return null;
        if (
          lines.slice(0, i).filter((previous) => previous.startsWith("```"))
            .length % 2
        )
          return <pre key={i}>{line || " "}</pre>;
        if (/^#{1,6} /.test(line))
          return <h3 key={i}>{line.replace(/^#+ /, "")}</h3>;
        if (/^[-*] /.test(line))
          return (
            <p key={i} className="bullet">
              {line.slice(2)}
            </p>
          );
        return line ? <p key={i}>{line}</p> : null;
      })}
    </div>
  );
}
