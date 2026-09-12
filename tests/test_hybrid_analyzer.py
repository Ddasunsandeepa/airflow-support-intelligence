from backend.app.hybrid_analyzer import analyze_hybrid
from backend.app.kubernetes_evidence import KubernetesEvidence


def test_kubernetes_and_llm_agreement(monkeypatch):
    def fake_llm(*args, **kwargs):
        return {
            "status": "success",
            "incident_class": "Kubernetes",
            "confidence": 0.95,
            "reasoning": "Explicit Kubernetes failure evidence.",
            "supporting_evidence": [
                "CrashLoopBackOff detected."
            ],
            "l1_checks": [],
            "escalation_needed": True,
            "escalation_reason": "Escalate if restart loop persists.",
        }

    monkeypatch.setattr(
        "backend.app.hybrid_analyzer.analyze_with_llm",
        fake_llm,
    )

    kubernetes = KubernetesEvidence(
        pod_status="CrashLoopBackOff",
        restart_count=5,
        exit_code=137,
    )

    result = analyze_hybrid(
        evidence={},
        ml_result={},
        kubernetes_evidence=kubernetes,
    )

    assert result["decision_mode"] == "K8S_LLM_AGREEMENT"
    assert result["final_class"] == "Kubernetes"
    assert result["human_review"] is False


def test_kubernetes_and_llm_conflict_requires_human_review(monkeypatch):
    def fake_llm(*args, **kwargs):
        return {
            "status": "success",
            "incident_class": "Resource",
            "confidence": 0.90,
            "reasoning": "Resource-related evidence.",
            "supporting_evidence": [],
            "l1_checks": [],
            "escalation_needed": True,
            "escalation_reason": "Review manually.",
        }

    monkeypatch.setattr(
        "backend.app.hybrid_analyzer.analyze_with_llm",
        fake_llm,
    )

    kubernetes = KubernetesEvidence(
        pod_status="CrashLoopBackOff",
        restart_count=5,
        exit_code=137,
    )

    result = analyze_hybrid(
        evidence={},
        ml_result={},
        kubernetes_evidence=kubernetes,
    )

    assert result["decision_mode"] == "K8S_LLM_CONFLICT"
    assert result["final_class"] == "Kubernetes"
    assert result["human_review"] is True


def test_kubernetes_evidence_only_requires_human_review(monkeypatch):
    def fake_llm(*args, **kwargs):
        return {
            "status": "not_configured",
            "incident_class": "Unknown",
            "confidence": None,
        }

    monkeypatch.setattr(
        "backend.app.hybrid_analyzer.analyze_with_llm",
        fake_llm,
    )

    kubernetes = KubernetesEvidence(
        pod_status="CrashLoopBackOff",
        restart_count=5,
        exit_code=137,
    )

    result = analyze_hybrid(
        evidence={},
        ml_result={},
        kubernetes_evidence=kubernetes,
    )

    assert result["decision_mode"] == "K8S_EVIDENCE_ONLY"
    assert result["final_class"] == "Kubernetes"
    assert result["human_review"] is True