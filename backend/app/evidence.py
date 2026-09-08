from dataclasses import dataclass
from typing import Optional


@dataclass
class AirflowEvidence:
    # ---------------------------------------------------------
    # Existing ML-oriented features
    # ---------------------------------------------------------

    heartbeat_status: Optional[int] = None
    dag_parse_time: Optional[float] = None
    scheduler_pod_status: Optional[int] = None
    worker_restarts: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    recent_changes: Optional[int] = None

    # ---------------------------------------------------------
    # Airflow operational evidence
    # ---------------------------------------------------------

    dag_count: int = 0
    paused_dag_count: int = 0
    stale_dag_count: int = 0
    dag_import_error_count: int = 0

    latest_dag_run_state: Optional[str] = None
    latest_dag_run_duration: Optional[float] = None

    task_count: int = 0
    failed_task_count: int = 0
    successful_task_count: int = 0

    # ---------------------------------------------------------
    # Failed task evidence
    # ---------------------------------------------------------

    failed_task_id: Optional[str] = None
    failed_task_operator: Optional[str] = None
    failed_task_duration: Optional[float] = None
    failed_task_try_number: Optional[int] = None

    # ---------------------------------------------------------
    # Failure log evidence
    # ---------------------------------------------------------

    failure_log_event: Optional[str] = None
    failure_exception_type: Optional[str] = None
    failure_exception_message: Optional[str] = None