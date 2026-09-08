from backend.app.evidence import AirflowEvidence
from backend.app.runbook import get_runbook


def analyze_airflow_evidence(evidence: AirflowEvidence) -> dict:
    """
    Analyze Airflow-native operational evidence.

    This layer detects operational incidents from evidence
    retrieved directly from Airflow. It does not fabricate
    unavailable ML features or claim unsupported root causes.
    """

    incident_detected = False
    incident_class = "Unknown"
    classification_confidence = None

    reasons = []

    # ---------------------------------------------------------
    # 1. Detect failed DAG/task execution
    # ---------------------------------------------------------

    if (
        evidence.latest_dag_run_state == "failed"
        and evidence.failed_task_count > 0
    ):
        incident_detected = True

        reasons.append(
            "The latest Airflow DAG run failed."
        )

        reasons.append(
            f"{evidence.failed_task_count} task(s) "
            "are reported as failed."
        )

    # ---------------------------------------------------------
    # 2. Failed task details
    # ---------------------------------------------------------

    if evidence.failed_task_id:
        reasons.append(
            f"Failed task: {evidence.failed_task_id}."
        )

    if evidence.failed_task_operator:
        reasons.append(
            f"Task operator: {evidence.failed_task_operator}."
        )

    if evidence.failed_task_duration is not None:
        reasons.append(
            f"Failed task duration: "
            f"{evidence.failed_task_duration:.3f} seconds."
        )

    if evidence.failed_task_try_number is not None:
        reasons.append(
            f"Failure occurred on try "
            f"{evidence.failed_task_try_number}."
        )

    # ---------------------------------------------------------
    # 3. Failure log evidence
    # ---------------------------------------------------------

    if evidence.failure_log_event:
        reasons.append(
            f"Airflow log event: "
            f"{evidence.failure_log_event}."
        )

    if evidence.failure_exception_type:
        reasons.append(
            f"Exception type: "
            f"{evidence.failure_exception_type}."
        )

    if evidence.failure_exception_message:
        reasons.append(
            f"Exception message: "
            f"{evidence.failure_exception_message}."
        )

    # ---------------------------------------------------------
    # 4. Scheduler health context
    # ---------------------------------------------------------

    if evidence.heartbeat_status == 0:
        reasons.append(
            "The Airflow scheduler heartbeat is unhealthy."
        )

    elif evidence.heartbeat_status == 1:
        reasons.append(
            "The Airflow scheduler heartbeat is healthy."
        )

    # ---------------------------------------------------------
    # 5. DAG parsing context
    # ---------------------------------------------------------

    if evidence.dag_import_error_count > 0:
        reasons.append(
            f"{evidence.dag_import_error_count} DAG(s) "
            "have import errors."
        )

    else:
        reasons.append(
            "No DAG import errors were reported."
        )

    # ---------------------------------------------------------
    # 6. Task execution context
    # ---------------------------------------------------------

    if evidence.task_count > 0:
        reasons.append(
            f"{evidence.task_count} task instance(s) "
            "were observed in the inspected latest runs."
        )

    # ---------------------------------------------------------
    # 7. Classification status
    # ---------------------------------------------------------

    if incident_detected:
        classification_status = (
            "Incident detected, but the available Airflow "
            "evidence does not establish a specific root-cause "
            "class."
        )
    else:
        classification_status = (
            "No failed DAG execution was detected in the "
            "available Airflow evidence."
        )

    # ---------------------------------------------------------
    # 8. Runbook
    # ---------------------------------------------------------

    runbook = get_runbook(incident_class)

    # ---------------------------------------------------------
    # 9. L1 guidance
    # ---------------------------------------------------------

    l1_checks = [
        "Identify the failed DAG run and affected task.",
        "Review the failed task logs for the error message and traceback.",
        "Check whether the failure is isolated to one DAG or affects multiple DAGs.",
        "Verify Airflow scheduler and DAG processor health.",
        "Review recent DAG, configuration, deployment, or dependency changes.",
    ]

    # ---------------------------------------------------------
    # 10. Escalation guidance
    # ---------------------------------------------------------

    if incident_detected:
        decision = (
            "Proceed with L1 investigation using the available "
            "failed DAG/task evidence. Do not assign a specific "
            "root-cause class until sufficient evidence is available."
        )
    else:
        decision = (
            "No active failed DAG execution was detected. "
            "Continue monitoring or gather additional evidence "
            "if an incident was reported."
        )

    return {
        "incident_detected": incident_detected,
        "incident_class": incident_class,
        "classification_confidence": classification_confidence,
        "classification_status": classification_status,
        "reasons": reasons,
        "runbook": runbook["runbook"],
        "runbook_status": runbook["status"],
        "runbook_content": runbook["content"],
        "l1_checks": l1_checks,
        "decision": decision,
    }


if __name__ == "__main__":
    from backend.app.airflow_adapter import AirflowAdapter

    adapter = AirflowAdapter()

    evidence = adapter.get_evidence()

    result = analyze_airflow_evidence(evidence)

    print("\n=== AIRFLOW SUPPORT INTELLIGENCE ===\n")

    print(
        f"Incident Detected : "
        f"{result['incident_detected']}"
    )

    print(
        f"Incident Class    : "
        f"{result['incident_class']}"
    )

    print(
        f"Classification    : "
        f"{result['classification_confidence']}"
    )

    print(
        f"Runbook           : "
        f"{result['runbook']}"
    )

    print(
        f"Runbook Status    : "
        f"{result['runbook_status']}"
    )

    print("\n=== CLASSIFICATION STATUS ===\n")

    print(result["classification_status"])

    print("\n=== EVIDENCE REASONS ===\n")

    for reason in result["reasons"]:
        print(f"- {reason}")

    print("\n=== L1 CHECKS ===\n")

    for index, check in enumerate(
        result["l1_checks"],
        start=1,
    ):
        print(f"{index}. {check}")

    print("\n=== ESCALATION ===\n")

    print(result["decision"])