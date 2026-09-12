from backend.app.kubernetes_evidence import KubernetesEvidence


def analyze_kubernetes_evidence(
    evidence: KubernetesEvidence | None,
) -> dict:
    """
    Analyze explicit Kubernetes evidence.

    This analyzer does not infer a Kubernetes incident from the
    DAG name or from a generic task failure. It only produces a
    classification when explicit Kubernetes evidence is present.
    """

    if evidence is None:
        return {
            "status": "no_kubernetes_evidence",
            "incident_class": "Unknown",
            "confidence": None,
            "reasoning": (
                "No Kubernetes evidence is available for "
                "this incident."
            ),
            "supporting_evidence": [],
        }

    pod_status = evidence.pod_status
    restart_count = evidence.restart_count
    exit_code = evidence.exit_code

    # ---------------------------------------------------------
    # CrashLoopBackOff
    # ---------------------------------------------------------

    if pod_status == "CrashLoopBackOff":
        supporting_evidence = [
            "Kubernetes pod status is CrashLoopBackOff.",
        ]

        if restart_count is not None:
            supporting_evidence.append(
                f"Kubernetes restart count is {restart_count}."
            )

        if exit_code is not None:
            supporting_evidence.append(
                f"Kubernetes container exit code is {exit_code}."
            )

        return {
            "status": "success",
            "incident_class": "Kubernetes",
            "confidence": 1.0,
            "reasoning": (
                "The evidence explicitly reports a "
                "CrashLoopBackOff pod state."
            ),
            "supporting_evidence": supporting_evidence,
        }

    # ---------------------------------------------------------
    # ImagePullBackOff
    # ---------------------------------------------------------

    if pod_status == "ImagePullBackOff":
        supporting_evidence = [
            "Kubernetes pod status is ImagePullBackOff.",
        ]

        if restart_count is not None:
            supporting_evidence.append(
                f"Kubernetes restart count is {restart_count}."
            )

        if exit_code is not None:
            supporting_evidence.append(
                f"Kubernetes container exit code is {exit_code}."
            )

        return {
            "status": "success",
            "incident_class": "Kubernetes",
            "confidence": 1.0,
            "reasoning": (
                "The evidence explicitly reports an "
                "ImagePullBackOff pod state."
            ),
            "supporting_evidence": supporting_evidence,
        }

    # ---------------------------------------------------------
    # Kubernetes evidence exists but does not identify a class
    # ---------------------------------------------------------

    if (
        pod_status is not None
        or restart_count is not None
        or exit_code is not None
    ):
        return {
            "status": "insufficient_kubernetes_evidence",
            "incident_class": "Unknown",
            "confidence": None,
            "reasoning": (
                "Kubernetes-related evidence is present, "
                "but it does not contain a recognized failure "
                "state that is sufficient for classification."
            ),
            "supporting_evidence": [],
        }

    return {
        "status": "no_kubernetes_evidence",
        "incident_class": "Unknown",
        "confidence": None,
        "reasoning": (
            "No explicit Kubernetes failure evidence "
            "was detected."
        ),
        "supporting_evidence": [],
    }