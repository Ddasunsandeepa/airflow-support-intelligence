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
        else "The controlled configuration evidence indicates invalid configuration."
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