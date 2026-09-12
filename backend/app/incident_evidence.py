from dataclasses import dataclass
from typing import Optional

from backend.app.evidence import AirflowEvidence
from backend.app.kubernetes_evidence import KubernetesEvidence


@dataclass
class IncidentEvidence:
    """
    Unified evidence model for an Airflow incident.

    Evidence remains separated by source so that Airflow,
    Kubernetes, monitoring, and change-history signals can
    evolve independently.
    """

    airflow: Optional[AirflowEvidence] = None
    kubernetes: Optional[KubernetesEvidence] = None