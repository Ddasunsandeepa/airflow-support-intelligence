from dataclasses import dataclass
from typing import Optional


@dataclass
class KubernetesEvidence:
    """
    Structured Kubernetes-related evidence.

    This model represents evidence that can be obtained from
    Kubernetes telemetry or, for the current proof of concept,
    explicitly structured synthetic task logs.
    """

    pod_status: Optional[str] = None
    restart_count: Optional[int] = None
    exit_code: Optional[int] = None
    container_ready: Optional[bool] = None