from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_analyze_airflow_returns_kubernetes_incident(monkeypatch):
    def fake_get_incident_evidence(self, dag_id=None):
        from backend.app.evidence import AirflowEvidence
        from backend.app.incident_evidence import IncidentEvidence
        from backend.app.kubernetes_evidence import KubernetesEvidence

        return IncidentEvidence(
            airflow=AirflowEvidence(
                heartbeat_status=1,
                dag_parse_time=0.125,
                worker_restarts=5,
                latest_dag_run_state="failed",
                failed_task_count=1,
                failure_exception_type="RuntimeError",
                failure_exception_message=(
                    "Synthetic Kubernetes failure detected: "
                    "PodStatus=CrashLoopBackOff, "
                    "RestartCount=5, "
                    "ExitCode=137"
                ),
            ),
            kubernetes=KubernetesEvidence(
                pod_status="CrashLoopBackOff",
                restart_count=5,
                exit_code=137,
            ),
        )

    def fake_llm(*args, **kwargs):
        return {
            "status": "success",
            "incident_class": "Kubernetes",
            "confidence": 0.95,
            "reasoning": "Explicit Kubernetes failure evidence.",
            "supporting_evidence": [
                "CrashLoopBackOff detected."
            ],
            "l1_checks": [
                "Inspect the affected pod."
            ],
            "escalation_needed": True,
            "escalation_reason": "Escalate if the restart loop persists.",
        }

    monkeypatch.setattr(
        "backend.app.main.AirflowAdapter.get_incident_evidence",
        fake_get_incident_evidence,
    )

    monkeypatch.setattr(
        "backend.app.hybrid_analyzer.analyze_with_llm",
        fake_llm,
    )

    response = client.post(
        "/analyze-airflow?dag_id=support_intelligence_kubernetes_failure"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["incident"]["detected"] is True
    assert data["incident"]["class"] == "Kubernetes"
    assert data["incident"]["decision_mode"] == "K8S_LLM_AGREEMENT"
    assert data["incident"]["agreement"] is True
    assert data["incident"]["human_review"] is False

    assert data["kubernetes"]["pod_status"] == "CrashLoopBackOff"
    assert data["kubernetes"]["restart_count"] == 5
    assert data["kubernetes"]["exit_code"] == 137

    assert data["llm"]["incident_class"] == "Kubernetes"
    assert data["llm"]["status"] == "success"