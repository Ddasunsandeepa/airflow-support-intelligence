from pathlib import Path


# Project root:
# D:\Projects\airflow-support-intelligence
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Runbooks directory
RUNBOOKS_DIR = PROJECT_ROOT / "runbooks"


# Mapping between ML incident classes and runbook files
RUNBOOK_MAP = {
    "Scheduler": "scheduler.md",
    "DAG Parsing": "dag_parsing.md",
    "Resource": "resource.md",
    "Kubernetes": "kubernetes.md",
    "Configuration": "configuration.md",
    "Unknown": "unknown.md",
}


def get_runbook(incident_class: str) -> dict:
    """
    Retrieve the runbook associated with an incident class.
    """

    filename = RUNBOOK_MAP.get(incident_class)

    if filename is None:
        return {
            "incident_class": incident_class,
            "runbook": None,
            "content": None,
            "status": "not_found",
        }

    runbook_path = RUNBOOKS_DIR / filename

    if not runbook_path.exists():
        return {
            "incident_class": incident_class,
            "runbook": filename,
            "content": None,
            "status": "file_not_found",
        }

    content = runbook_path.read_text(encoding="utf-8")

    return {
        "incident_class": incident_class,
        "runbook": filename,
        "content": content,
        "status": "success",
    }