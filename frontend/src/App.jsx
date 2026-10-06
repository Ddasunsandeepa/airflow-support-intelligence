import { useState } from "react";
import { useRoute, useResource, incidentPath } from "./api";
import { Overview, Incidents, ManualAnalysis } from "./ConsolePages";
import IncidentWorkspace from "./IncidentWorkspace";
import SourceRemediationWorkspace from "./SourceRemediationWorkspace";
import SourceRemediationHistory from "./SourceRemediationHistory";
import { Badge, Empty } from "./ui";

export default function App() {
  const route = useRoute();
  const path = route.split("?")[0];
  const parts = path.split("/").filter(Boolean);
  const catalog = useResource("/airflow-catalog");
  const health = useResource("/health", 30000);
  const reviews = useResource("/source-remediations", 15000);
  const feed = useResource("/incident-feed", 30000);
  const [observations, setObservations] = useState({});
  const [collapsed, setCollapsed] = useState(false);
  const current =
    parts[0] === "incidents" && parts.length >= 3
      ? { type: parts[1], id: decodeURIComponent(parts[2]) }
      : null;
  const [lastIncident, setLastIncident] = useState(null);
  const context = current || lastIncident;
  const links = [
    ["/overview", "Overview"],
    ["/incidents", "Incidents"],
    [
      context ? incidentPath(context.type, context.id) : "/investigation",
      "Investigation",
    ],
    [
      context ? incidentPath(context.type, context.id, "copilot") : "/copilot",
      "Developer Copilot",
    ],
    [
      context
        ? incidentPath(context.type, context.id, "remediation")
        : "/remediation",
      "Remediation",
    ],
    ["/reviews", "Source Reviews"],
    ["/audit", "Audit & feedback"],
  ];
  function analyzed(type, id, data) {
    setObservations((old) => ({
      ...old,
      [`${type}/${id}`]: { type, id, data },
    }));
    setLastIncident({ type, id });
  }
  let content;
  if (path === "/overview" || path === "/")
    content = (
      <Overview {...{ catalog, health, reviews, observations, feed }} />
    );
  else if (path === "/incidents")
    content = <Incidents {...{ catalog, observations }} />;
  else if (current)
    content = (
      <IncidentWorkspace
        key={`${current.type}/${current.id}`}
        {...current}
        tab={parts[3] || "investigation"}
        onAnalyzed={analyzed}
      />
    );
  else if (parts[0] === "reviews" && parts[1])
    content = (
      <>
        <a href="#/reviews" className="back-link">
          Back to Source Reviews
        </a>
        <SourceRemediationWorkspace key={parts[1]} proposalId={parts[1]} />
      </>
    );
  else if (path === "/reviews" || path === "/audit")
    content = (
      <SourceRemediationHistory
        key={route}
        audit={path === "/audit"}
        dagId={new URLSearchParams(route.split("?")[1] || "").get("dag") || ""}
      />
    );
  else if (path === "/manual") content = <ManualAnalysis />;
  else
    content = (
      <Empty title="Choose an incident">
        <a href="#/incidents">Open the incident catalog</a> to investigate
        evidence, use Copilot or review operational actions.
      </Empty>
    );
  return (
    <div className={`console ${collapsed ? "compact" : ""}`}>
      <a
        className="skip"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content").focus();
        }}
      >
        Skip to content
      </a>
      <header className="topbar">
        <button
          className="nav-toggle"
          aria-label="Toggle navigation"
          onClick={() => setCollapsed(!collapsed)}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M4 6h16M4 12h16M4 18h16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
          </svg>
        </button>
        <a className="brand" href="#/overview">
          Airflow <span>Support Intelligence</span>
        </a>
        <div className="topbar-status">
          <span>Local PoC</span>
          <Badge>
            {health.error
              ? "API unavailable"
              : health.data
                ? "API healthy"
                : "Checking API"}
          </Badge>
        </div>
      </header>
      <aside className="sidebar">
        <p className="nav-label">Workspace</p>
        <nav aria-label="Primary navigation">
          {links.map(([href, label]) => (
            <a
              key={label}
              href={`#${href}`}
              aria-current={
                path === href ||
                (label === "Source Reviews" && parts[0] === "reviews")
                  ? "page"
                  : undefined
              }
            >
              {label}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <a href="#/manual">Manual evidence tool</a>
          <small>AI proposes. Engineers decide.</small>
          <small>Local reviewer roles are self-declared.</small>
        </div>
      </aside>
      <main id="main-content" tabIndex={-1}>
        {content}
      </main>
    </div>
  );
}
