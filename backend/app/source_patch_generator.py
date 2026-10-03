from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourcePatchSuggestion:
    function_name: str
    proposed_function: str
    summary: str
    reason: str
    generated_by: str


def generate_source_patch(
    dag_id: str,
    incident_class: Optional[str] = None,
    failure_message: Optional[str] = None,
) -> Optional[SourcePatchSuggestion]:
    """
    Generate a review-only source patch suggestion.

    Current phase:
    controlled deterministic fallback.

    Future phase:
    evidence-grounded LLM generation can be added here without
    changing source retrieval, diff generation, or the review UI.

    This function does not read, write, execute, or deploy files.
    """

    if dag_id == "support_intelligence_configuration_review_demo":
        return _configuration_patch(
            incident_class=incident_class,
            failure_message=failure_message,
        )

    if dag_id == "support_intelligence_supervisor_demo":
        return _supervisor_demo_change(failure_message)
    if dag_id == "support_intelligence_kubernetes_resource_demo":
        return _kubernetes_resource_demo_change(failure_message)
    return None


def _configuration_patch(
    incident_class: Optional[str],
    failure_message: Optional[str],
) -> SourcePatchSuggestion:
    proposed_function = '''def configuration_review_demo(**context):
    """
    Validate the controlled synthetic service configuration
    before continuing with the demonstration workflow.
    """

    dag_run = context.get("dag_run")
    mode = "failure"

    if dag_run and dag_run.conf:
        mode = dag_run.conf.get("mode", "failure")

    service_endpoint = "https://service.internal"
    environment = "production"
    timeout_seconds = 30

    if not service_endpoint:
        raise ValueError(
            "Service endpoint configuration is required."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "Timeout configuration must be greater than zero."
        )

    print(
        "CONFIGURATION VALIDATION: "
        f"ServiceEndpoint={service_endpoint}, "
        f"Environment={environment}, "
        f"TimeoutSeconds={timeout_seconds}"
    )

    if mode == "recovery":
        print(
            "CONFIGURATION DEMO RECOVERY: "
            "Synthetic configuration validation completed successfully."
        )
        return "recovered"

    return "healthy"'''

    evidence_description = (
        failure_message.strip()
        if failure_message
        else "Controlled configuration demo template; confirm it against the observed evidence."
    )

    return SourcePatchSuggestion(
        function_name="configuration_review_demo",
        proposed_function=proposed_function,
        summary=(
            "Propose a reviewed source-level correction for the "
            "controlled configuration failure demonstration DAG."
        ),
        reason=(
            f"{evidence_description} "
            "The proposed change supplies valid configuration values "
            "and validates them before the task continues."
        ),
        generated_by="controlled_fallback",
    )

def _supervisor_demo_change(failure_message: str | None) -> SourcePatchSuggestion:
    proposed_function = '''def supervisor_demo_incident(**context):
    dag_run = context.get("dag_run")
    mode = "failure"

    if dag_run and dag_run.conf:
        mode = dag_run.conf.get("mode", "failure")

    synthetic_pod_status = "Healthy"
    synthetic_restart_count = 0
    synthetic_exit_code = 0

    if mode == "recovery":
        print("SUPERVISOR DEMO RECOVERY: Synthetic incident recovery completed successfully.")
        return "recovered"

    if synthetic_pod_status != "Healthy":
        raise RuntimeError(
            "Synthetic supervisor demo failure detected: "
            f"PodStatus={synthetic_pod_status}, "
            f"RestartCount={synthetic_restart_count}, "
            f"ExitCode={synthetic_exit_code}"
        )

    return "healthy"'''
    return SourcePatchSuggestion(
        function_name="supervisor_demo_incident",
        proposed_function=proposed_function,
        summary="Proposed source-level correction for the controlled synthetic demo.",
        reason=(failure_message or "Review the controlled synthetic failure.")
        + " This deterministic proposal remains review-only.",
        generated_by="controlled_fallback",
    )


def _kubernetes_resource_demo_change(failure_message: str | None) -> SourcePatchSuggestion:
    proposed_function = '''def kubernetes_resource_demo(**context):
    dag_run = context.get("dag_run")
    mode = "failure"

    if dag_run and dag_run.conf:
        mode = dag_run.conf.get("mode", "failure")

    synthetic_pod_status = "Running"
    synthetic_restart_count = 0
    synthetic_exit_code = 0

    if mode == "recovery":
        print(
            "SUPPORT_INTELLIGENCE_K8S: "
            f"PodStatus={synthetic_pod_status} "
            f"RestartCount={synthetic_restart_count} "
            f"ExitCode={synthetic_exit_code}"
        )

        print(
            "KUBERNETES RESOURCE DEMO RECOVERY: "
            "Synthetic workload recovered successfully."
        )

        return "recovered"

    if synthetic_pod_status != "Running":
        raise RuntimeError(
            "Synthetic Kubernetes resource failure detected: "
            f"PodStatus={synthetic_pod_status}, "
            f"RestartCount={synthetic_restart_count}, "
            f"ExitCode={synthetic_exit_code}"
        )

    print(
        "KUBERNETES RESOURCE DEMO HEALTHY: "
        "Synthetic Kubernetes workload is healthy."
    )

    return "healthy"'''
    return SourcePatchSuggestion(
        function_name="kubernetes_resource_demo",
        proposed_function=proposed_function,
        summary="Proposed source-level correction for the controlled synthetic demo.",
        reason=(failure_message or "Review the controlled synthetic failure.")
        + " This deterministic proposal remains review-only.",
        generated_by="controlled_fallback",
    )
