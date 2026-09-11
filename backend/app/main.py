from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from backend.app.analyze import (
    analyze_incident,
    analyze_airflow_with_ml,
)
from backend.app.runbook import get_runbook
from backend.app.recommendation import generate_recommendation
from backend.app.airflow_adapter import AirflowAdapter
from backend.app.hybrid_analyzer import analyze_hybrid

from backend.app.action_models import (
    ActionRequest,
    RemediationAction,
)
from backend.app.action_service import ActionService
from backend.app.actions.airflow import AirflowActionExecutor

from backend.app.approval import approve_action, reject_action
from backend.app.action_store import ActionStore


app = FastAPI(
    title="Airflow Support Intelligence",
    description="AI-assisted L1 Airflow incident investigation and support guidance",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# V2 Controlled Remediation Service
# --------------------------------------------------

action_service = ActionService(
    airflow_executor=AirflowActionExecutor()
)

action_store = ActionStore()


class IncidentEvidence(BaseModel):
    cpu_usage: float
    memory_usage: float
    heartbeat_status: int
    dag_parse_time: float
    recent_changes: int
    scheduler_pod_status: int
    worker_restarts: int


def evidence_to_dict(evidence):
    return {
        key: value
        for key, value in vars(evidence).items()
    }


def build_guidance(final_class, final_confidence, ml_result, llm_result):
    final_runbook = get_runbook(final_class)

    final_recommendation = generate_recommendation(
        incident_class=final_class,
        confidence=final_confidence or 0.0,
        explanation=ml_result.get("explanation", []),
    )

    if llm_result.get("status") == "success":
        l1_checks = llm_result.get("l1_checks", [])
    else:
        l1_checks = final_recommendation["l1_checks"]

    if llm_result.get("status") == "success":
        escalation_needed = llm_result.get(
            "escalation_needed",
            True,
        )
        escalation_reason = llm_result.get(
            "escalation_reason",
            "",
        )
    else:
        escalation_needed = True
        escalation_reason = final_recommendation["decision"]

    return {
        "runbook": final_runbook["runbook"],
        "runbook_status": final_runbook["status"],
        "runbook_content": final_runbook["content"],
        "l1_checks": l1_checks,
        "escalation": {
            "needed": escalation_needed,
            "recommendation": escalation_reason,
        },
    }



# --------------------------------------------------
# Automatic live incident detection
# --------------------------------------------------

incident_detector_initialized = False
seen_failed_runs = set()


def _run_value(run, *keys):
    for key in keys:
        value = run.get(key)
        if value is not None:
            return value
    return None


@app.get("/incident-feed")
def incident_feed():
    """
    Detect newly failed Airflow DAG runs.

    The first poll establishes a baseline of failures that already existed.
    Later polls report only a DAG run that has newly entered the failed state.
    No automatic remediation is performed.
    """
    global incident_detector_initialized

    adapter = AirflowAdapter()
    catalog = adapter.get_catalog()

    current_failed = []

    for dag in catalog.get("dags", []):
        dag_id = dag.get("dag_id")
        if not dag_id:
            continue

        try:
            runs_response = adapter.get_dag_runs(dag_id, limit=10)

            if isinstance(runs_response, dict):
                runs = runs_response.get("dag_runs", [])
            elif isinstance(runs_response, list):
                runs = runs_response
            else:
                runs = []

        except Exception:
            continue
        

        for run in runs or []:
            if not isinstance(run, dict):
                continue
            state = _run_value(run, "state")
            if state != "failed":
                continue

            run_id = _run_value(run, "dag_run_id", "run_id")
            if not run_id:
                continue

            current_failed.append(
                {
                    "dag_id": dag_id,
                    "run_id": str(run_id),
                    "state": state,
                    "logical_date": _run_value(
                        run,
                        "logical_date",
                        "run_after",
                        "start_date",
                    ),
                }
            )

    if not incident_detector_initialized:
        seen_failed_runs.update(
            (item["dag_id"], item["run_id"]) for item in current_failed
        )
        incident_detector_initialized = True
        return {
            "new_incident": False,
            "incident": None,
            "message": "Incident detector baseline established.",
        }

    for item in current_failed:
        key = (item["dag_id"], item["run_id"])

        if key not in seen_failed_runs:
            seen_failed_runs.add(key)
            return {
                "new_incident": True,
                "incident": item,
                "message": "New failed Airflow DAG run detected.",
            }

    return {
        "new_incident": False,
        "incident": None,
        "message": "No new failed Airflow DAG run detected.",
    }


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


@app.get("/airflow-catalog")
def airflow_catalog():
    """
    Return the current Airflow incident catalog.

    Registered DAGs come from /api/v2/dags.
    Parsing/import errors come from /api/v2/importErrors.

    This keeps the frontend dynamic and prevents hardcoded DAG names.
    """
    adapter = AirflowAdapter()
    catalog = adapter.get_catalog()

    dags = catalog["dags"]
    import_errors = catalog["import_errors"]

    dag_options = [
        {
            "type": "dag",
            "id": dag.get("dag_id"),
            "label": dag.get("dag_id"),
            "status": "registered",
            "has_import_errors": dag.get(
                "has_import_errors",
                False,
            ),
            "is_paused": dag.get("is_paused"),
            "is_stale": dag.get("is_stale"),
        }
        for dag in dags
        if dag.get("dag_id")
    ]

    import_error_options = [
        {
            "type": "import_error",
            "id": str(
                error.get("id")
                or error.get("import_error_id")
            ),
            "label": (
                error.get("filename")
                or error.get("bundle_name")
                or "DAG parsing error"
            ),
            "status": "parsing_error",
            "filename": error.get("filename"),
            "bundle_name": error.get("bundle_name"),
            "timestamp": error.get("timestamp"),
        }
        for error in import_errors
        if error.get("id") is not None
        or error.get("import_error_id") is not None
    ]

    return {
        "source": "local_airflow",
        "registered_dags": dag_options,
        "import_errors": import_error_options,
        "total_registered_dags": len(dag_options),
        "total_import_errors": len(import_error_options),
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
        "evidence": evidence_to_dict(evidence),
    }


@app.post("/actions/{action_id}/approve")
def approve_remediation_action(
    action_id: str,
    approved_by: str = "l1-approver",
    approver_role: str = "L1",
    comment: str | None = None,
):
    """
    Approve a validated remediation action.
    """

    remediation = action_store.get(action_id)

    if remediation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Action '{action_id}' was not found.",
        )

    try:
        remediation = approve_action(
            remediation=remediation,
            approved_by=approved_by,
            approver_role=approver_role,
            comment=comment,
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    action_store.save(remediation)

    return remediation.model_dump(mode="json")


@app.post("/actions/{action_id}/execute")
def execute_remediation_action(action_id: str):
    """
    Execute an approved remediation action and verify the result.
    """

    remediation = action_store.get(action_id)

    if remediation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Action '{action_id}' was not found.",
        )

    try:
        result = action_service.execute(remediation)

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        action_store.save(remediation)

        raise HTTPException(
            status_code=500,
            detail=f"Action execution failed: {exc}",
        ) from exc

    action_store.save(remediation)

    return {
        "action": remediation.model_dump(mode="json"),
        "result": result,
    }

@app.get("/actions/{action_id}")
def get_action(action_id: str):
    """
    Retrieve the current state of a remediation action.
    """

    remediation = action_store.get(action_id)

    if remediation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Action '{action_id}' was not found.",
        )

    return remediation.model_dump(mode="json")

# --------------------------------------------------
# V2 Controlled Remediation
# --------------------------------------------------

@app.post("/actions")
def create_action(
    action: ActionRequest,
    user_role: str = "L1",
    created_by: str = "l1-user",
):
    """
    Create and validate a controlled remediation action.

    No Airflow action is executed here.
    """

    adapter = AirflowAdapter()

    catalog = adapter.get_catalog()

    available_dags = {
        dag.get("dag_id")
        for dag in catalog.get("dags", [])
        if dag.get("dag_id")
    }

    remediation = action_service.create_action(
        action=action,
        created_by=created_by,
    )

    remediation = action_service.validate(
        remediation=remediation,
        user_role=user_role,
        available_dags=available_dags,
    )
    action_store.save(remediation)

    return remediation.model_dump(mode="json")

@app.post("/analyze-airflow")
def analyze_airflow(dag_id: str | None = None):
    adapter = AirflowAdapter()

    # --------------------------------------------------
    # 1. Collect live Airflow evidence
    # --------------------------------------------------

    evidence = adapter.get_evidence(dag_id=dag_id)

    evidence_dict = evidence_to_dict(evidence)

    # --------------------------------------------------
    # 2. Run ML + SHAP when enough features exist
    # --------------------------------------------------

    ml_result = analyze_airflow_with_ml(evidence)

    # --------------------------------------------------
    # 3. Run hybrid ML + LLM analysis
    # --------------------------------------------------

    hybrid_result = analyze_hybrid(
        evidence=evidence_dict,
        ml_result=ml_result,
    )

    # --------------------------------------------------
    # 4. Resolve final guidance
    # --------------------------------------------------

    final_class = hybrid_result["final_class"]
    final_confidence = hybrid_result["final_confidence"]
    llm_result = hybrid_result["llm"]

    guidance = build_guidance(
        final_class=final_class,
        final_confidence=final_confidence,
        ml_result=ml_result,
        llm_result=llm_result,
    )

    # --------------------------------------------------
    # Final response
    # --------------------------------------------------

    return {
        "source": "local_airflow",
        "requested_dag_id": dag_id,

        "incident": {
            "detected": (
                evidence.latest_dag_run_state == "failed"
                or evidence.failed_task_count > 0
            ),
            "class": final_class,
            "classification_confidence": final_confidence,
            "decision_mode": hybrid_result["decision_mode"],
            "agreement": hybrid_result["agreement"],
            "human_review": hybrid_result["human_review"],
        },

        "ml": ml_result,

        "llm": llm_result,

        "evidence": evidence_dict,

        "guidance": {
            "runbook": guidance["runbook"],
            "runbook_status": guidance["runbook_status"],
            "runbook_content": guidance["runbook_content"],
            "l1_checks": guidance["l1_checks"],
        },

        "escalation": guidance["escalation"],
    }


@app.post("/analyze-import-error")
def analyze_import_error(import_error_id: str):
    """
    Analyze an Airflow DAG parsing/import error.

    Parsing-failed DAGs are not registered, so they cannot be analyzed
    through /analyze-airflow?dag_id=...
    """
    adapter = AirflowAdapter()

    try:
        error = adapter.get_import_error(import_error_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to retrieve Airflow import error: {exc}",
        ) from exc

    exception_message = (
        error.get("stack_trace")
        or error.get("error")
        or error.get("message")
        or "Airflow DAG parsing/import error detected."
    )

    evidence = {
        "heartbeat_status": None,
        "dag_parse_time": None,
        "scheduler_pod_status": None,
        "worker_restarts": None,
        "cpu_usage": None,
        "memory_usage": None,
        "recent_changes": None,

        "dag_count": 0,
        "paused_dag_count": 0,
        "stale_dag_count": 0,
        "dag_import_error_count": 1,

        "latest_dag_run_state": None,
        "latest_dag_run_duration": None,

        "task_count": 0,
        "failed_task_count": 0,
        "successful_task_count": 0,

        "failed_task_id": None,
        "failed_task_operator": None,
        "failed_task_duration": None,
        "failed_task_try_number": None,

        "failure_log_event": "DAG import/parsing error",
        "failure_exception_type": "DAGImportError",
        "failure_exception_message": exception_message,

        "import_error_id": str(
            error.get("id")
            or error.get("import_error_id")
            or import_error_id
        ),
        "import_error_filename": error.get("filename"),
        "import_error_bundle": error.get("bundle_name"),
        "import_error_timestamp": error.get("timestamp"),
    }

    # ML cannot make a structured classification here because the
    # infrastructure features required by the trained model are absent.
    ml_result = {
        "status": "insufficient_features",
        "incident_class": "Unknown",
        "confidence": None,
        "explanation": [],
        "missing_features": [
            "cpu_usage",
            "memory_usage",
            "recent_changes",
            "scheduler_pod_status",
            "worker_restarts",
        ],
        "runbook": None,
        "runbook_status": None,
        "runbook_content": None,
        "recommendation": None,
    }

    hybrid_result = analyze_hybrid(
        evidence=evidence,
        ml_result=ml_result,
    )

    final_class = hybrid_result["final_class"]
    final_confidence = hybrid_result["final_confidence"]
    llm_result = hybrid_result["llm"]

    guidance = build_guidance(
        final_class=final_class,
        final_confidence=final_confidence,
        ml_result=ml_result,
        llm_result=llm_result,
    )

    return {
        "source": "local_airflow",
        "incident_type": "import_error",
        "requested_import_error_id": import_error_id,

        "incident": {
            "detected": True,
            "class": final_class,
            "classification_confidence": final_confidence,
            "decision_mode": hybrid_result["decision_mode"],
            "agreement": hybrid_result["agreement"],
            "human_review": hybrid_result["human_review"],
        },

        "ml": ml_result,
        "llm": llm_result,
        "evidence": evidence,

        "guidance": {
            "runbook": guidance["runbook"],
            "runbook_status": guidance["runbook_status"],
            "runbook_content": guidance["runbook_content"],
            "l1_checks": guidance["l1_checks"],
        },

        "escalation": guidance["escalation"],
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
