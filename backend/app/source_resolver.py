from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DAG_SOURCE_ROOT = PROJECT_ROOT.parent / "airflow" / "dags"


def resolve_dag_source(
    dag_id: str,
) -> Optional[Path]:
    """
    Resolve a DAG ID to a local DAG source file.

    Read-only resolver:
    - does not modify files
    - does not execute files
    - does not allow arbitrary paths
    - only searches inside the configured DAG directory
    """

    if not dag_id or not dag_id.strip():
        return None

    dag_id = dag_id.strip()

    # Normal Airflow convention used by our demo DAGs.
    candidate = DAG_SOURCE_ROOT / f"{dag_id}.py"

    try:
        resolved_candidate = candidate.resolve()
        resolved_root = DAG_SOURCE_ROOT.resolve()

        # Prevent path traversal outside dags/.
        resolved_candidate.relative_to(resolved_root)

    except (ValueError, OSError):
        return None

    if not resolved_candidate.is_file():
        return None

    return resolved_candidate


def read_dag_source(
    dag_id: str,
) -> Optional[str]:
    """
    Safely read the source of a locally available DAG.

    This function never writes to the source file.
    """

    source_path = resolve_dag_source(dag_id)

    if source_path is None:
        return None

    try:
        return source_path.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError):
        return None


def get_relative_dag_path(
    dag_id: str,
) -> Optional[str]:
    """
    Return a display-safe DAG path.

    The returned path is relative to the configured
    Airflow DAG source root.
    """

    source_path = resolve_dag_source(dag_id)

    if source_path is None:
        return None

    try:
        relative_path = source_path.relative_to(
            DAG_SOURCE_ROOT.resolve()
        )

        return (
            Path("dags") / relative_path
        ).as_posix()

    except ValueError:
        return None