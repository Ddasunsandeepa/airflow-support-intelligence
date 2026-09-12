from dataclasses import asdict

from backend.app.incident_evidence import IncidentEvidence


def build_intelligence_features(
    evidence: IncidentEvidence,
) -> dict:
    """
    Convert unified incident evidence into structured
    intelligence features.

    This function derives features from explicitly available
    Airflow and Kubernetes evidence.

    It does not invent missing telemetry.
    """

    features = {}

    # ---------------------------------------------------------
    # Airflow features
    # ---------------------------------------------------------

    if evidence.airflow is not None:
        airflow = asdict(evidence.airflow)

        features.update({
            "cpu_usage": airflow.get("cpu_usage"),
            "memory_usage": airflow.get("memory_usage"),
            "heartbeat_status": airflow.get("heartbeat_status"),
            "dag_parse_time": airflow.get("dag_parse_time"),
            "recent_changes": airflow.get("recent_changes"),
            "scheduler_pod_status": airflow.get(
                "scheduler_pod_status"
            ),
            "worker_restarts": airflow.get("worker_restarts"),
        })

    # ---------------------------------------------------------
    # Kubernetes features
    # ---------------------------------------------------------

    kubernetes = evidence.kubernetes

    features["kubernetes_present"] = (
        1 if kubernetes is not None else 0
    )

    features["kubernetes_pod_status"] = None
    features["kubernetes_restart_count"] = None
    features["kubernetes_exit_code"] = None

    features["kubernetes_pod_failure"] = 0
    features["kubernetes_image_pull_failure"] = 0

    if kubernetes is not None:

        features["kubernetes_pod_status"] = (
            kubernetes.pod_status
        )

        features["kubernetes_restart_count"] = (
            kubernetes.restart_count
        )

        features["kubernetes_exit_code"] = (
            kubernetes.exit_code
        )

        # -----------------------------------------------------
        # Explicit Kubernetes failure states
        # -----------------------------------------------------

        if kubernetes.pod_status in {
            "CrashLoopBackOff",
            "ImagePullBackOff",
        }:
            features["kubernetes_pod_failure"] = 1

        if kubernetes.pod_status == "ImagePullBackOff":
            features["kubernetes_image_pull_failure"] = 1

    return features