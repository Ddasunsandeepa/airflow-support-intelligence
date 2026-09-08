from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from backend.app.analyze import analyze_incident
from backend.app.airflow_adapter import AirflowAdapter
from backend.app.airflow_analyzer import analyze_airflow_evidence


app = FastAPI(
    title="Airflow Support Intelligence",
    description="AI-assisted L1 Airflow incident investigation and support guidance",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncidentEvidence(BaseModel):
    cpu_usage: float
    memory_usage: float
    heartbeat_status: int
    dag_parse_time: float
    recent_changes: int
    scheduler_pod_status: int
    worker_restarts: int


@app.get("/")
def root():
    return {
        "service": "Airflow Support Intelligence",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/airflow-evidence")
def airflow_evidence():
    """
    Retrieve live operational evidence from the local Airflow instance.
    """

    adapter = AirflowAdapter()

    evidence = adapter.get_evidence()

    return {
        "source": "local_airflow",
        "evidence": {
            "heartbeat_status": evidence.heartbeat_status,
            "dag_parse_time": evidence.dag_parse_time,
            "scheduler_pod_status": evidence.scheduler_pod_status,
            "worker_restarts": evidence.worker_restarts,
            "cpu_usage": evidence.cpu_usage,
            "memory_usage": evidence.memory_usage,
            "recent_changes": evidence.recent_changes,
            "dag_count": evidence.dag_count,
            "paused_dag_count": evidence.paused_dag_count,
            "stale_dag_count": evidence.stale_dag_count,
            "dag_import_error_count": evidence.dag_import_error_count,
            "latest_dag_run_state": evidence.latest_dag_run_state,
            "latest_dag_run_duration": evidence.latest_dag_run_duration,
            "task_count": evidence.task_count,
            "failed_task_count": evidence.failed_task_count,
            "successful_task_count": evidence.successful_task_count,
        },
    }

@app.post("/analyze-airflow")
def analyze_airflow():
    """
    Analyze the current operational state of the local Airflow instance.
    """

    adapter = AirflowAdapter()

    evidence = adapter.get_evidence()

    result = analyze_airflow_evidence(evidence)

    return {
        "source": "local_airflow",

        "incident": {
            "detected": result["incident_detected"],
            "class": result["incident_class"],
            "classification_confidence": (
                result["classification_confidence"]
            ),
            "classification_status": (
                result["classification_status"]
            ),
        },

        "evidence": {
            "heartbeat_status": evidence.heartbeat_status,
            "dag_count": evidence.dag_count,
            "dag_import_error_count": (
                evidence.dag_import_error_count
            ),
            "latest_dag_run_state": (
                evidence.latest_dag_run_state
            ),
            "latest_dag_run_duration": (
                evidence.latest_dag_run_duration
            ),
            "task_count": evidence.task_count,
            "failed_task_count": (
                evidence.failed_task_count
            ),
            "successful_task_count": (
                evidence.successful_task_count
            ),
            "failed_task_id": evidence.failed_task_id,
            "failed_task_operator": (
                evidence.failed_task_operator
            ),
            "failed_task_duration": (
                evidence.failed_task_duration
            ),
            "failed_task_try_number": (
                evidence.failed_task_try_number
            ),
            "failure_log_event": (
                evidence.failure_log_event
            ),
            "failure_exception_type": (
                evidence.failure_exception_type
            ),
            "failure_exception_message": (
                evidence.failure_exception_message
            ),
        },

        "analysis": {
            "reasons": result["reasons"],
        },

        "guidance": {
            "runbook": result["runbook"],
            "runbook_status": result["runbook_status"],
            "runbook_content": result["runbook_content"],
            "l1_checks": result["l1_checks"],
        },

        "escalation": {
            "recommendation": result["decision"],
        },
    }


@app.post("/analyze")
def analyze(evidence: IncidentEvidence):

    incident = evidence.model_dump()

    result = analyze_incident(incident)

    recommendation = result["recommendation"]

    return {
        "incident": {
            "class": result["incident_class"],
            "confidence": result["confidence"],
        },

        "explanation": {
            "top_contributors": recommendation["top_evidence"],
        },

        "guidance": {
            "runbook": result["runbook"],
            "runbook_status": result["runbook_status"],
            "runbook_content": result["runbook_content"],
            "l1_checks": recommendation["l1_checks"],
        },

        "escalation": {
            "recommendation": recommendation["decision"],
        },
    }