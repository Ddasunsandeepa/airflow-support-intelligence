from datetime import datetime
from typing import Any


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an Airflow ISO-8601 timestamp."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _timeline_event(
    *,
    timestamp: str | None,
    event_type: str,
    title: str,
    description: str,
    source: str,
    severity: str = "info",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one normalized timeline event."""
    return {
        "timestamp": timestamp,
        "event_type": event_type,
        "title": title,
        "description": description,
        "source": source,
        "severity": severity,
        "metadata": metadata or {},
    }


def build_incident_timeline(
    dag_run: dict[str, Any],
    task_instances: list[dict[str, Any]],
    task_logs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Build a chronological incident timeline from observed Airflow data.

    Timestamps are only taken from source data. This function does not
    invent timestamps for events that do not have an observed timestamp.
    """

    events: list[dict[str, Any]] = []

    # ---------------------------------------------------------
    # DAG RUN
    # ---------------------------------------------------------

    if dag_run.get("queued_at"):
        events.append(
            _timeline_event(
                timestamp=dag_run.get("queued_at"),
                event_type="dag_queued",
                title="DAG run queued",
                description=(
                    f"DAG run '{dag_run.get('dag_run_id')}' "
                    "was queued."
                ),
                source="airflow.dag_run",
                metadata={
                    "dag_id": dag_run.get("dag_id"),
                    "dag_run_id": dag_run.get("dag_run_id"),
                    "state": dag_run.get("state"),
                },
            )
        )

    if dag_run.get("start_date"):
        events.append(
            _timeline_event(
                timestamp=dag_run.get("start_date"),
                event_type="dag_started",
                title="DAG run started",
                description=(
                    f"DAG '{dag_run.get('dag_id')}' "
                    "started execution."
                ),
                source="airflow.dag_run",
                metadata={
                    "dag_id": dag_run.get("dag_id"),
                    "dag_run_id": dag_run.get("dag_run_id"),
                },
            )
        )

    # ---------------------------------------------------------
    # TASK INSTANCES
    # ---------------------------------------------------------

    for task in task_instances:
        task_id = task.get("task_id")

        if task.get("queued_when"):
            events.append(
                _timeline_event(
                    timestamp=task.get("queued_when"),
                    event_type="task_queued",
                    title="Task queued",
                    description=(
                        f"Task '{task_id}' was queued."
                    ),
                    source="airflow.task_instance",
                    metadata={
                        "task_id": task_id,
                        "dag_id": task.get("dag_id"),
                        "dag_run_id": task.get("dag_run_id"),
                        "operator": task.get("operator"),
                        "try_number": task.get("try_number"),
                    },
                )
            )

        elif task.get("run_after"):
            events.append(
                _timeline_event(
                    timestamp=task.get("run_after"),
                    event_type="task_scheduled",
                    title="Task scheduled",
                    description=(
                        f"Task '{task_id}' was scheduled."
                    ),
                    source="airflow.task_instance",
                    metadata={
                        "task_id": task_id,
                        "operator": task.get("operator"),
                    },
                )
            )

        if task.get("start_date"):
            events.append(
                _timeline_event(
                    timestamp=task.get("start_date"),
                    event_type="task_started",
                    title="Task started",
                    description=(
                        f"Task '{task_id}' started execution."
                    ),
                    source="airflow.task_instance",
                    metadata={
                        "task_id": task_id,
                        "operator": task.get("operator"),
                        "try_number": task.get("try_number"),
                    },
                )
            )

        if (
            task.get("state") in {"failed", "upstream_failed"}
            and task.get("end_date")
        ):
            events.append(
                _timeline_event(
                    timestamp=task.get("end_date"),
                    event_type="task_failed",
                    title="Task failed",
                    description=(
                        f"Task '{task_id}' finished with state "
                        f"'{task.get('state')}'."
                    ),
                    source="airflow.task_instance",
                    severity="error",
                    metadata={
                        "task_id": task_id,
                        "state": task.get("state"),
                        "operator": task.get("operator"),
                        "try_number": task.get("try_number"),
                        "duration": task.get("duration"),
                    },
                )
            )

    # ---------------------------------------------------------
    # TASK LOG EVENTS
    # ---------------------------------------------------------

    for log_entry in task_logs or []:
        if not isinstance(log_entry, dict):
            continue

        timestamp = log_entry.get("timestamp")
        event_name = log_entry.get("event")

        if not timestamp or not event_name:
            continue

        error_details = log_entry.get("error_detail")

        if event_name == "Task failed with exception":
            exception_type = None
            exception_message = None

            if isinstance(error_details, list) and error_details:
                first_error = error_details[0]

                if isinstance(first_error, dict):
                    exception_type = first_error.get("exc_type")
                    exception_message = first_error.get("exc_value")

            events.append(
                _timeline_event(
                    timestamp=timestamp,
                    event_type="failure_exception",
                    title="Failure exception observed",
                    description=(
                        exception_message
                        or "Airflow reported a task exception."
                    ),
                    source="airflow.task_log",
                    severity="error",
                    metadata={
                        "exception_type": exception_type,
                        "exception_message": exception_message,
                        "task_id": log_entry.get("task_id"),
                        "dag_id": log_entry.get("dag_id"),
                        "try_number": log_entry.get("try_number"),
                    },
                )
            )

    # ---------------------------------------------------------
    # DAG RUN END
    # ---------------------------------------------------------

    if dag_run.get("end_date"):
        state = dag_run.get("state")

        events.append(
            _timeline_event(
                timestamp=dag_run.get("end_date"),
                event_type="dag_finished",
                title="DAG run finished",
                description=(
                    f"DAG run finished with state '{state}'."
                ),
                source="airflow.dag_run",
                severity=(
                    "error"
                    if state in {"failed", "upstream_failed"}
                    else "info"
                ),
                metadata={
                    "dag_id": dag_run.get("dag_id"),
                    "dag_run_id": dag_run.get("dag_run_id"),
                    "state": state,
                    "duration": dag_run.get("duration"),
                },
            )
        )

    # ---------------------------------------------------------
    # CHRONOLOGICAL ORDER
    # ---------------------------------------------------------

    events.sort(
        key=lambda event: (
            _parse_timestamp(event.get("timestamp"))
            or datetime.max,
        )
    )

    return events