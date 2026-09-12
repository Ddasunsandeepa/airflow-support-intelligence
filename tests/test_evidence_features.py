from backend.app.evidence import AirflowEvidence
from backend.app.evidence_features import build_intelligence_features
from backend.app.incident_evidence import IncidentEvidence
from backend.app.kubernetes_evidence import KubernetesEvidence


def test_crashloopbackoff_features_are_extracted():
    evidence = IncidentEvidence(
        airflow=AirflowEvidence(
            heartbeat_status=1,
            dag_parse_time=0.125,
            worker_restarts=5,
        ),
        kubernetes=KubernetesEvidence(
            pod_status="CrashLoopBackOff",
            restart_count=5,
            exit_code=137,
        ),
    )

    features = build_intelligence_features(evidence)

    assert features["kubernetes_present"] == 1
    assert features["kubernetes_pod_status"] == "CrashLoopBackOff"
    assert features["kubernetes_restart_count"] == 5
    assert features["kubernetes_exit_code"] == 137
    assert features["kubernetes_pod_failure"] == 1
    assert features["kubernetes_image_pull_failure"] == 0
    assert features["worker_restarts"] == 5


def test_imagepullbackoff_features_are_extracted():
    evidence = IncidentEvidence(
        airflow=AirflowEvidence(
            heartbeat_status=1,
            dag_parse_time=0.233,
            worker_restarts=0,
        ),
        kubernetes=KubernetesEvidence(
            pod_status="ImagePullBackOff",
            restart_count=0,
            exit_code=1,
        ),
    )

    features = build_intelligence_features(evidence)

    assert features["kubernetes_present"] == 1
    assert features["kubernetes_pod_status"] == "ImagePullBackOff"
    assert features["kubernetes_restart_count"] == 0
    assert features["kubernetes_exit_code"] == 1
    assert features["kubernetes_pod_failure"] == 1
    assert features["kubernetes_image_pull_failure"] == 1


def test_no_kubernetes_evidence_is_handled_safely():
    evidence = IncidentEvidence(
        airflow=AirflowEvidence(
            heartbeat_status=1,
            dag_parse_time=0.1,
        ),
        kubernetes=None,
    )

    features = build_intelligence_features(evidence)

    assert features["kubernetes_present"] == 0
    assert features["kubernetes_pod_status"] is None
    assert features["kubernetes_restart_count"] is None
    assert features["kubernetes_exit_code"] is None
    assert features["kubernetes_pod_failure"] == 0
    assert features["kubernetes_image_pull_failure"] == 0