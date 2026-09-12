import re

from backend.app.kubernetes_evidence import KubernetesEvidence


def parse_kubernetes_evidence(text: str) -> KubernetesEvidence:
    """
    Extract explicitly structured Kubernetes evidence from text.

    The parser does not infer Kubernetes state.
    It only extracts values that are explicitly present.
    """

    if not isinstance(text, str):
        return KubernetesEvidence()

    pod_status = None
    restart_count = None
    exit_code = None

    # ---------------------------------------------------------
    # Pod status
    #
    # Example:
    # PodStatus=CrashLoopBackOff
    # PodStatus=ImagePullBackOff
    # ---------------------------------------------------------

    pod_match = re.search(
        r"PodStatus\s*=\s*([A-Za-z0-9_-]+)",
        text,
    )

    if pod_match:
        pod_status = pod_match.group(1)

    # ---------------------------------------------------------
    # Restart count
    #
    # Example:
    # RestartCount=5
    # ---------------------------------------------------------

    restart_match = re.search(
        r"RestartCount\s*=\s*(\d+)",
        text,
    )

    if restart_match:
        restart_count = int(restart_match.group(1))

    # ---------------------------------------------------------
    # Exit code
    #
    # Example:
    # ExitCode=137
    # ---------------------------------------------------------

    exit_match = re.search(
        r"ExitCode\s*=\s*(-?\d+)",
        text,
    )

    if exit_match:
        exit_code = int(exit_match.group(1))

    return KubernetesEvidence(
        pod_status=pod_status,
        restart_count=restart_count,
        exit_code=exit_code,
    )