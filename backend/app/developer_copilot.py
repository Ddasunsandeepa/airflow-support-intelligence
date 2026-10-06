from backend.app.airflow_adapter import AirflowAdapter
from backend.app.analyze import analyze_airflow_with_ml
from backend.app.developer_models import (
    CodeChangeProposal,
    DeveloperChatResponse,
    DiagnosisResult,
)
from backend.app.hybrid_analyzer import analyze_hybrid

from backend.app.developer_llm import analyze_with_developer_llm



def _evidence_to_dict(evidence):
    """
    Convert the Airflow evidence dataclass into a dictionary
    that can be passed through the existing intelligence layers.
    """

    return {
        key: value
        for key, value in vars(evidence).items()
    }


def _build_evidence_summary(evidence, kubernetes_evidence):
    """
    Build concise developer-facing evidence statements.

    Only evidence actually collected from the current Airflow
    environment is included.
    """

    statements = []

    if evidence.latest_dag_run_state:
        statements.append(
            f"Latest DAG run state: "
            f"{evidence.latest_dag_run_state}"
        )

    if evidence.failed_task_count:
        statements.append(
            f"Failed task count: "
            f"{evidence.failed_task_count}"
        )

    if evidence.failed_task_id:
        statements.append(
            f"Failed task: "
            f"{evidence.failed_task_id}"
        )

    if evidence.failed_task_operator:
        statements.append(
            f"Failed task operator: "
            f"{evidence.failed_task_operator}"
        )

    if evidence.failure_exception_type:
        statements.append(
            f"Exception type: "
            f"{evidence.failure_exception_type}"
        )

    if evidence.failure_exception_message:
        statements.append(
            f"Failure message: "
            f"{evidence.failure_exception_message}"
        )

    if kubernetes_evidence is not None:
        if kubernetes_evidence.pod_status:
            statements.append(
                f"Kubernetes pod status: "
                f"{kubernetes_evidence.pod_status}"
            )

        if kubernetes_evidence.restart_count is not None:
            statements.append(
                f"Kubernetes restart count: "
                f"{kubernetes_evidence.restart_count}"
            )

        if kubernetes_evidence.exit_code is not None:
            statements.append(
                f"Kubernetes exit code: "
                f"{kubernetes_evidence.exit_code}"
            )

    return statements

def _build_import_error_evidence_summary(error):
    """
    Build concise developer-facing evidence statements for
    an Airflow DAG parsing/import error.
    """

    statements = []

    filename = error.get("filename")
    bundle_name = error.get("bundle_name")
    timestamp = error.get("timestamp")
    stack_trace = (
        error.get("stack_trace")
        or error.get("error")
        or error.get("message")
    )

    if filename:
        statements.append(
            f"Import error filename: {filename}"
        )

    if bundle_name:
        statements.append(
            f"Airflow bundle: {bundle_name}"
        )

    if timestamp:
        statements.append(
            f"Import error timestamp: {timestamp}"
        )

    statements.append(
        "Failure event: DAG import/parsing error"
    )

    if stack_trace:
        statements.append(
            f"Import error stack trace: {stack_trace}"
        )

    return statements

def _build_recommended_fix(incident_class):
    """
    Provide conservative developer guidance based on the
    final incident classification.

    This function does not generate or apply code changes.
    """

    recommendations = {
        "DAG Parsing": (
            "Inspect the DAG import path, Python dependencies, "
            "syntax, and configuration referenced by the DAG."
        ),
        "Kubernetes": (
            "Inspect the affected Kubernetes workload, pod state, "
            "container events, restart history, and resource or "
            "image-related configuration."
        ),
        "Resource": (
            "Inspect CPU and memory pressure, worker capacity, "
            "task concurrency, and workload resource configuration."
        ),
        "Scheduler": (
            "Inspect scheduler health, heartbeat status, scheduler "
            "logs, and scheduler workload conditions."
        ),
        "Configuration": (
            "Inspect recent configuration changes and verify the "
            "affected Airflow or deployment configuration."
        ),
        "Application Code": (
            "Inspect the failing task's source code and the runtime condition that caused "
            "the Python exception. If the defect is source-level, prepare a reviewed source "
            "remediation proposal when source resolves safely. Applying it requires separate execution policy approval."
        ),
        "Unknown": (
            "The available evidence is insufficient for a specific "
            "developer fix. Continue investigation before changing code."
        ),
    }

    return recommendations.get(
        incident_class,
        recommendations["Unknown"],
    )


def _build_code_change_proposal(
    incident_class,
    evidence,
):
    """
    Decide whether a code change proposal is appropriate.

    Version 1 intentionally does not generate source-code patches.
    It only establishes the safety boundary for future code generation.
    """

    if incident_class == "DAG Parsing":
        return CodeChangeProposal(
            available=False,
            summary=(
                "A code-level fix may be appropriate, but source "
                "generation is not enabled in this first Copilot version."
            ),
            reason=(
                "DAG parsing incidents can originate from DAG source "
                "code or Python dependencies. A later version can "
                "generate a reviewed patch from the affected DAG source."
            ),
        )

    return CodeChangeProposal(
        available=False,
        summary="No source-code patch proposed.",
        reason=(
            "The current incident classification does not justify "
            "an automatic source-code change proposal."
        ),
    )


def _build_tests(incident_class):
    """
    Suggest validation activities for the developer.

    These are recommendations only; the Copilot does not execute
    the tests in this version.
    """

    tests_by_class = {
        "DAG Parsing": [
            "Validate DAG import/parsing successfully.",
            "Run the affected DAG's Python tests if available.",
        ],
        "Kubernetes": [
            "Validate the affected workload configuration.",
            "Confirm the workload reaches a healthy pod state.",
        ],
        "Resource": [
            "Validate task resource requirements.",
            "Confirm worker CPU and memory capacity.",
        ],
        "Scheduler": [
            "Confirm scheduler health and heartbeat.",
            "Verify the affected DAG can be scheduled normally.",
        ],
        "Configuration": [
            "Validate the changed configuration.",
            "Confirm the affected DAG or component starts normally.",
        ],
        "Application Code": [
            "Validate proposed Python syntax without executing the DAG.",
            "Validate DAG structure and the affected task/function mapping.",
            "Reproduce or test the failing input condition and confirm edge-case handling.",
            "Require validation and human approval of the exact source revision before application.",
            "Confirm Airflow parses the reviewed DAG before execution, then verify the corrected task.",
        ],
        "Unknown": [
            "Collect additional logs and infrastructure evidence.",
            "Re-run incident analysis after additional evidence is available.",
        ],
    }

    return tests_by_class.get(
        incident_class,
        tests_by_class["Unknown"],
    )


def analyze_developer_request(
    message: str,
    incident_type: str = "dag",
    dag_id: str | None = None,
    import_error_id: str | None = None,
    allow_demo_fallback: bool = False,
) -> DeveloperChatResponse:
    """
    Analyze a developer request using live Airflow evidence.

    The Copilot supports:
    - registered DAG incidents
    - DAG parsing/import errors

    The Copilot is advisory only. It does not modify DAG source
    files or execute operational actions.
    """

    if not message.strip():
        raise ValueError("Developer message cannot be empty.")

    if incident_type not in {"dag", "import_error"}:
        raise ValueError(
            "Unsupported incident type. "
            "Expected 'dag' or 'import_error'."
        )

    adapter = AirflowAdapter()

    # --------------------------------------------------
    # Registered DAG investigation
    # --------------------------------------------------

    if incident_type == "dag":
        if not dag_id or not dag_id.strip():
            raise ValueError(
                "dag_id is required for DAG incidents."
            )

        incident_evidence = adapter.get_incident_evidence(
            dag_id=dag_id
        )

        airflow_evidence = incident_evidence.airflow
        kubernetes_evidence = incident_evidence.kubernetes

        evidence_dict = _evidence_to_dict(
            airflow_evidence
        )

        ml_result = analyze_airflow_with_ml(
            airflow_evidence
        )

        hybrid_result = analyze_hybrid(
            evidence=evidence_dict,
            ml_result=ml_result,
            kubernetes_evidence=kubernetes_evidence,
        )

        incident_class = hybrid_result["final_class"]
        confidence = hybrid_result["final_confidence"]

        evidence_summary = _build_evidence_summary(
            airflow_evidence,
            kubernetes_evidence,
        )

        incident_reference = dag_id

    # --------------------------------------------------
    # DAG parsing/import error investigation
    # --------------------------------------------------

    else:
        if not import_error_id or not import_error_id.strip():
            raise ValueError(
                "import_error_id is required for import-error incidents."
            )

        try:
            import_error = adapter.get_import_error(
                import_error_id
            )
        except Exception as exc:
            raise ValueError(
                f"Unable to retrieve Airflow import error: {exc}"
            ) from exc

        evidence_summary = _build_import_error_evidence_summary(
            import_error
        )

        # An Airflow import-error record is itself direct evidence
        # that the failure occurred during DAG parsing/import.
        incident_class = "DAG Parsing"

        # This is a deterministic classification from the Airflow
        # import-error source, not a calibrated ML probability.
        confidence = None

        airflow_evidence = None

        incident_reference = (
            import_error.get("filename")
            or f"import_error:{import_error_id}"
        )

        ml_result = {
            "status": "not_applicable",
            "incident_class": "DAG Parsing",
            "confidence": None,
            "explanation": [],
        }

    # --------------------------------------------------
    # Common developer reasoning
    # --------------------------------------------------

    diagnosis = DiagnosisResult(
        incident_class=incident_class,
        summary=(
            f"The available Airflow evidence is most consistent "
            f"with a {incident_class} incident."
        ),
        confidence=confidence,
    )

    recommended_fix = _build_recommended_fix(
        incident_class
    )

    code_change = CodeChangeProposal(available=False, generated_by="no_proposal",
                                     summary="No reviewed source proposal available.")
    source_outcome = None
    if incident_type == "dag" and dag_id and airflow_evidence.failed_task_id:
        from backend.app.source_review_validation import resolve_review_source
        from backend.app.source_updater import read_exact
        from backend.app.ai_source_investigation import investigate_source
        from backend.app.source_remediation import SourceRemediationService
        from backend.app.evidence_signals import extract_evidence_signals
        from dataclasses import asdict
        import json
        try:
            path = resolve_review_source(dag_id)
            source = read_exact(path)
            code_change.before_code = source
            code_change.file_path = f"dags/{dag_id}.py"
            code_change.target = dag_id
            try:
                timeline_data = adapter.get_incident_timeline_data(dag_id)
                # Bounded actual log excerpt; retain task/run metadata separately.
                timeline_data = dict(timeline_data)
                logs = timeline_data.pop("task_logs", [])
                log_excerpt = json.dumps(logs, default=str)[:20000]
            except Exception:
                timeline_data, log_excerpt = {}, "Task timeline/log retrieval unavailable."
            context = {
                "developer_request": message, "incident_class": incident_class,
                "evidence_summary": evidence_summary, "airflow_evidence": evidence_dict,
                "ml_result": ml_result,
                "evidence_signals": asdict(extract_evidence_signals(evidence_dict, kubernetes_evidence)),
                "hybrid_analysis": hybrid_result, "timeline": timeline_data, "task_log_excerpt": log_excerpt,
            }
            source_outcome = investigate_source(dag_id, source, context, allow_demo_fallback=allow_demo_fallback)
            if source_outcome["proposal"]:
                proposed, patch, provenance = source_outcome["proposal"]
                record = SourceRemediationService().create(
                    source, proposed, patch, provenance, context, dag_id=dag_id,
                    investigation=source_outcome.get("investigation"),
                )
                code_change = CodeChangeProposal(
                    available=True, summary=patch.summary, reason=patch.reasoning,
                    target=dag_id, file_path=record.change.source_code.file_path, language="python",
                    before_code=source, proposed_code=proposed, generated_by=provenance,
                    source_remediation_id=record.proposal_id,
                )
            else:
                code_change.reason = ("No AI source proposal: " + source_outcome["provider_status"]
                                      + ". " + source_outcome.get("validation_error", "Inspect provider status and investigation evidence."))
        except (ValueError, SyntaxError, OSError) as exc:
            code_change.reason = f"Source investigation could not be prepared: {exc}"

    tests_to_run = _build_tests(
        incident_class
    )

    if source_outcome is None:
        developer_llm_result = analyze_with_developer_llm(
            message=message,
            incident_type=incident_type,
            incident_reference=incident_reference,
            evidence=evidence_summary,
            incident_class=incident_class,
            confidence=confidence,
            recommended_fix=recommended_fix,
        )
    else:
        developer_llm_result = {"status": "source_investigation"}

    if developer_llm_result["status"] == "success":
        final_summary = developer_llm_result["summary"]
        final_reasoning = developer_llm_result["reasoning"]

        final_recommended_fix = developer_llm_result[
            "recommended_fix"
        ]

        if developer_llm_result["tests_to_run"]:
            tests_to_run = developer_llm_result["tests_to_run"]

        if developer_llm_result["code_change_summary"] and not code_change.available and incident_type != "dag":
            code_change = code_change.model_copy(
                update={
                    "summary": developer_llm_result[
                        "code_change_summary"
                    ],
                    "reason": (
                        developer_llm_result["code_change_summary"]
                        or code_change.reason
                    ),
                }
            )

    else:
        final_summary = diagnosis.summary

        final_reasoning = (
            "The response is based on the structured Airflow "
            "evidence. Developer-specific LLM reasoning is "
            "currently unavailable."
        )

        final_recommended_fix = recommended_fix

    investigation = (source_outcome or {}).get("investigation") or {}
    if investigation:
        final_summary = investigation["diagnosis"]
        final_reasoning = investigation["reasoning"]
        tests_to_run = investigation["tests_to_run"] or tests_to_run
        final_recommended_fix = investigation["change_summary"] or recommended_fix
    if source_outcome and source_outcome["provider_status"] != "success":
        final_reasoning += f" Source proposal provider status: {source_outcome['provider_status']}."

    return DeveloperChatResponse(
        status="success",
        message=message,
        incident_type=incident_type,
        dag_id=dag_id,
        import_error_id=import_error_id,
        diagnosis=DiagnosisResult(
            incident_class=incident_class,
            summary=final_summary,
            confidence=confidence,
        ),
        evidence=evidence_summary,
        reasoning=final_reasoning,
        recommended_fix=final_recommended_fix,
        code_change=code_change,
        tests_to_run=tests_to_run,
        root_cause=investigation.get("root_cause"), evidence_used=investigation.get("evidence_used", []),
        risks=investigation.get("risks", []), assumptions=investigation.get("assumptions", []),
        provider_status=(source_outcome or {}).get("provider_status"),
        provider_attempts=(source_outcome or {}).get("provider_attempts", []),
        proposal_status=code_change.generated_by or "no_proposal",
        human_review_required=True,
    )
