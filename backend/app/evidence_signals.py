from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceSignalResult:
    incident_class: str
    confidence: float
    matched_signals: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def extract_evidence_signals(
    evidence: dict[str, Any],
    kubernetes_evidence: Any = None,
) -> EvidenceSignalResult:
    """
    Infer an incident class from explicit operational evidence.

    This layer is deterministic and evidence-driven.
    It does not inspect DAG IDs and does not call an LLM.

    Priority: direct DAG import evidence; then the existing Kubernetes,
    parsing, explicit task MemoryError, configuration, scheduler and resource
    rules; then task-runtime application exceptions; otherwise Unknown. Confidence is rule strength,
    not a calibrated causal probability.
    """

    failure_message = _lower(
        evidence.get("failure_exception_message")
    )
    exception_type = _lower(
        evidence.get("failure_exception_type")
    )

    supporting_evidence: list[str] = []

    # Direct incident-specific import evidence takes precedence. A global import
    # error count is not proof that this failed task's DAG could not be imported.
    direct_import = (
        evidence.get("incident_type") == "import_error"
        or bool(evidence.get("import_error_filename"))
        or any(term in failure_message for term in ("broken dag", "dag import", "failed to import"))
    )
    if direct_import:
        return EvidenceSignalResult(
            incident_class="DAG Parsing", confidence=0.90,
            matched_signals=["direct_dag_import_evidence"],
            supporting_evidence=["Direct DAG import/parsing failure evidence was observed."]
            + ([f"Exception message: {_text(evidence.get('failure_exception_message'))}"] if failure_message else []),
        )

    # --------------------------------------------------
    # Kubernetes signals
    # --------------------------------------------------

    pod_status = ""
    restart_count = None
    exit_code = None

    if kubernetes_evidence is not None:
        if isinstance(kubernetes_evidence, dict):
            pod_status = _text(
                kubernetes_evidence.get("pod_status")
            )
            restart_count = kubernetes_evidence.get(
                "restart_count"
            )
            exit_code = kubernetes_evidence.get(
                "exit_code"
            )
        else:
            pod_status = _text(
                getattr(
                    kubernetes_evidence,
                    "pod_status",
                    None,
                )
            )
            restart_count = getattr(
                kubernetes_evidence,
                "restart_count",
                None,
            )
            exit_code = getattr(
                kubernetes_evidence,
                "exit_code",
                None,
            )

    kubernetes_signals: list[str] = []

    for term in ("crashloopbackoff", "imagepullbackoff", "errimagepull"):
        if term in failure_message:
            kubernetes_signals.append(term)
            supporting_evidence.append(f"Failure message reports Kubernetes state: {term}.")

    if pod_status.lower() in {
        "crashloopbackoff",
        "imagepullbackoff",
        "errimagepull",
        "oomkilled",
    }:
        kubernetes_signals.append(
            f"pod_status={pod_status}"
        )
        supporting_evidence.append(
            f"Kubernetes pod status is {pod_status}."
        )

    if isinstance(restart_count, int) and restart_count > 0:
        kubernetes_signals.append(
            f"restart_count={restart_count}"
        )
        supporting_evidence.append(
            f"Kubernetes restart count is {restart_count}."
        )

    if exit_code in {137, 143}:
        kubernetes_signals.append(
            f"exit_code={exit_code}"
        )
        supporting_evidence.append(
            f"Container exit code is {exit_code}."
        )

    if kubernetes_signals:
        return EvidenceSignalResult(
            incident_class="Kubernetes",
            confidence=0.95,
            matched_signals=kubernetes_signals,
            supporting_evidence=supporting_evidence,
        )

    # --------------------------------------------------
    # DAG parsing / import signals
    # --------------------------------------------------

    parsing_terms = (
        "broken dag",
        "failed to import",
        "importerror",
        "modulenotfounderror",
        "syntaxerror",
        "dag import",
        "dag parsing",
    )

    parsing_matches = [
        term
        for term in parsing_terms
        if term in failure_message
        or term in exception_type
    ]

    if parsing_matches:
        return EvidenceSignalResult(
            incident_class="DAG Parsing",
            confidence=0.90,
            matched_signals=parsing_matches,
            supporting_evidence=[
                (
                    "The failure evidence contains "
                    "DAG parsing or import-related signals."
                ),
                (
                    f"Exception type: "
                    f"{_text(evidence.get('failure_exception_type'))}"
                ),
            ],
        )

    # --------------------------------------------------
    # Explicit runtime memory failure is stronger than generic "configured" text.
    # Keep direct import and Kubernetes/container precedence above this rule.
    if exception_type == "memoryerror" and evidence.get("failed_task_id"):
        return EvidenceSignalResult(
            incident_class="Resource", confidence=0.90,
            matched_signals=["runtime_memory_error"],
            supporting_evidence=["Runtime exception: MemoryError",
                                 f"Failed task: {evidence['failed_task_id']}",
                                 f"Exception message: {_text(evidence.get('failure_exception_message'))}"],
        )

    # Configuration signals
    # --------------------------------------------------

    configuration_terms = (
        "configuration",
        "config",
        "missing endpoint",
        "required service endpoint",
        "invalid timeout",
        "timeout configuration",
        "missing environment",
        "invalid configuration",
        "connection configuration",
    )

    configuration_matches = [
        term
        for term in configuration_terms
        if term in failure_message
    ]

    if configuration_matches:
        message = _text(
            evidence.get("failure_exception_message")
        )

        return EvidenceSignalResult(
            incident_class="Configuration",
            confidence=0.90,
            matched_signals=configuration_matches,
            supporting_evidence=[
                (
                    f"Failure message: {message}"
                    if message
                    else
                    "Configuration-related failure evidence detected."
                )
            ],
        )

    # --------------------------------------------------
    # Scheduler signals
    # --------------------------------------------------

    scheduler_terms = (
        "scheduler heartbeat",
        "scheduler unavailable",
        "scheduler failure",
        "scheduler unhealthy",
    )

    scheduler_matches = [
        term
        for term in scheduler_terms
        if term in failure_message
    ]

    if scheduler_matches:
        return EvidenceSignalResult(
            incident_class="Scheduler",
            confidence=0.90,
            matched_signals=scheduler_matches,
            supporting_evidence=[
                "Scheduler-related failure evidence was detected."
            ],
        )

    # --------------------------------------------------
    # Resource signals
    # --------------------------------------------------

    resource_terms = (
        "out of memory",
        "oom",
        "memory pressure",
        "memory limit",
        "cpu limit",
        "cpu pressure",
        "resource exhausted",
    )

    resource_matches = [
        term
        for term in resource_terms
        if term in failure_message
    ]

    if resource_matches:
        return EvidenceSignalResult(
            incident_class="Resource",
            confidence=0.90,
            matched_signals=resource_matches,
            supporting_evidence=[
                (
                    f"Failure message: "
                    f"{_text(evidence.get('failure_exception_message'))}"
                )
            ],
        )

    # Application signals are deliberately last: they never override any of
    # the existing domain signals above. An operator name alone proves nothing.
    runtime_failure = bool(_text(evidence.get("failed_task_id"))) and (
        _lower(evidence.get("latest_dag_run_state")) == "failed"
        or isinstance(evidence.get("failed_task_count"), int) and evidence["failed_task_count"] > 0
    )
    runtime_exceptions = {
        "zerodivisionerror", "typeerror", "keyerror", "attributeerror",
        "indexerror", "nameerror", "unboundlocalerror",
    }
    # ValueError alone is ambiguous. Recognize explicit data transformation
    # failures only, after configuration and infrastructure have been checked.
    value_error_terms = (
        "invalid literal for int()", "could not convert string to float",
        "not enough values to unpack", "too many values to unpack",
        "math domain error", "no valid transaction amounts",
    )
    application_exception = exception_type in runtime_exceptions or (
        exception_type == "valueerror" and any(term in failure_message for term in value_error_terms)
    )
    if runtime_failure and application_exception:
        details = [
            f"Runtime exception: {_text(evidence.get('failure_exception_type'))}",
            f"Failed task: {_text(evidence.get('failed_task_id'))}",
        ]
        if failure_message:
            details.append(f"Exception message: {_text(evidence.get('failure_exception_message'))}")
        if _text(evidence.get("failed_task_operator")):
            details.append(f"Failed task operator: {_text(evidence.get('failed_task_operator'))}")
        return EvidenceSignalResult(
            incident_class="Application Code", confidence=0.90,
            matched_signals=["task_runtime_failure", f"exception_type={exception_type}"],
            supporting_evidence=details,
        )

    return EvidenceSignalResult(
        incident_class="Unknown",
        confidence=0.0,
        matched_signals=[],
        supporting_evidence=[],
    )
