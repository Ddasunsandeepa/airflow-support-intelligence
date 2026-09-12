from backend.app.kubernetes_analyzer import analyze_kubernetes_evidence
from backend.app.kubernetes_evidence import KubernetesEvidence


def test_crashloopbackoff_is_classified_as_kubernetes():
    evidence = KubernetesEvidence(
        pod_status="CrashLoopBackOff",
        restart_count=5,
        exit_code=137,
    )

    result = analyze_kubernetes_evidence(evidence)

    assert result["status"] == "success"
    assert result["incident_class"] == "Kubernetes"
    assert result["confidence"] == 1.0


def test_imagepullbackoff_is_classified_as_kubernetes():
    evidence = KubernetesEvidence(
        pod_status="ImagePullBackOff",
        restart_count=0,
        exit_code=1,
    )

    result = analyze_kubernetes_evidence(evidence)

    assert result["status"] == "success"
    assert result["incident_class"] == "Kubernetes"
    assert result["confidence"] == 1.0


def test_missing_kubernetes_evidence_returns_unknown():
    result = analyze_kubernetes_evidence(None)

    assert result["status"] == "no_kubernetes_evidence"
    assert result["incident_class"] == "Unknown"
    assert result["confidence"] is None


def test_unrecognized_kubernetes_state_returns_unknown():
    evidence = KubernetesEvidence(
        pod_status="Running",
        restart_count=0,
        exit_code=0,
    )

    result = analyze_kubernetes_evidence(evidence)

    assert result["status"] == "insufficient_kubernetes_evidence"
    assert result["incident_class"] == "Unknown"
    assert result["confidence"] is None