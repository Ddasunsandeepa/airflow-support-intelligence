"""Full demo flow against isolated stores and a simulated Airflow boundary."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from backend.app import main, developer_copilot, source_resolver, source_patch_generator
from backend.app.actions.airflow import AirflowActionExecutor
from backend.app.action_service import ActionService
from backend.app.evidence import AirflowEvidence
from backend.app.incident_evidence import IncidentEvidence
from backend.app.verification import VerificationEngine


DAG = "support_intelligence_configuration_review_demo"


@pytest.fixture
def demo_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setattr(source_resolver, "DAG_SOURCE_ROOT", tmp_path)
    source = tmp_path / f"{DAG}.py"
    source.write_text(
        'from airflow import DAG\nfrom airflow.providers.standard.operators.python import PythonOperator\n\n'
        'def configuration_review_demo(**context):\n    raise ValueError("required service endpoint is missing")\n\n'
        f'with DAG(dag_id="{DAG}", schedule=None) as dag:\n'
        '    task = PythonOperator(task_id="validate", python_callable=configuration_review_demo)\n',
        encoding="utf-8",
    )

    class DemoAirflow:
        calls = []

        def get_catalog(self):
            return {"dags": [{"dag_id": DAG, "is_paused": False}], "import_errors": []}

        def get_dags(self):
            return {"dags": [{"dag_id": DAG}]}

        def get_incident_evidence(self, dag_id=None):
            return IncidentEvidence(airflow=AirflowEvidence(
                latest_dag_run_state="failed", failed_task_count=1,
                failed_task_id="validate", failure_exception_type="ValueError",
                failure_exception_message="required service endpoint is missing; invalid timeout configuration",
            ), kubernetes=None)

        def get_incident_timeline_data(self, dag_id=None):
            return {"dag_run": {"dag_id": DAG, "dag_run_id": "demo-failure", "state": "failed",
                    "start_date": "2026-09-29T10:00:00Z", "end_date": "2026-09-29T10:01:00Z"},
                    "task_instances": [], "task_logs": []}

        def trigger_dag(self, dag_id, logical_date=None, conf=None):
            self.calls.append({"dag_id": dag_id, "conf": conf})
            return {"dag_run_id": "demo-recovery", "state": "queued"}

        def get_dag_runs(self, dag_id, limit=20):
            return {"dag_runs": [{"dag_run_id": "demo-recovery", "state": "success"}]}

    # This test models an external AI response, not a production patch selector.
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: {
        "status": "success", "result": {"status": "proposal", "diagnosis": "Configuration failure",
        "root_cause": "Missing endpoint", "reasoning": "The supplied function raises ValueError",
        "evidence_used": ["ValueError", "Actual source"], "target_function": "configuration_review_demo",
        "proposed_function": 'def configuration_review_demo(**context):\n    return {"endpoint_status": "reviewed"}',
        "change_summary": "Review endpoint handling", "tests_to_run": ["Verify endpoint configuration"],
        "risks": ["Engineer must supply actual endpoint policy"], "assumptions": []}})
    adapter = DemoAirflow()
    monkeypatch.setattr(main, "AirflowAdapter", lambda: adapter)
    monkeypatch.setattr(developer_copilot, "AirflowAdapter", lambda: adapter)
    service = ActionService(AirflowActionExecutor(adapter), VerificationEngine(adapter, poll_interval=0))
    monkeypatch.setattr(main, "action_service", service)
    return TestClient(main.app), source, adapter


def test_complete_supervisor_demo(demo_backend):
    client, source, adapter = demo_backend
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    analysis = client.post(f"/analyze-airflow?dag_id={DAG}")
    assert analysis.status_code == 200
    assert analysis.json()["incident"]["class"] == "Configuration"
    assert analysis.json()["timeline"]
    assert analysis.json()["evidence_signals"]["supporting_evidence"]
    copilot = client.post("/developer/chat", json={"message": "What should I investigate?", "dag_id": DAG}).json()
    proposal = copilot["code_change"]
    assert proposal["available"] and proposal["generated_by"] == "developer_llm"
    review = client.post("/change-proposals/source-code", json={
        **{key: proposal[key] for key in ("target", "file_path", "before_code", "proposed_code", "generated_by")},
        "description": proposal["reason"],
    })
    assert review.status_code == 200
    assert review.json()["source_code"]["before_code"] == source.read_bytes().decode("utf-8")
    assert review.json()["additions"] > 0
    assert adapter.calls == []
    action = client.post("/actions", json={"action_type": "trigger_dag", "dag_id": DAG,
        "parameters": {"mode": "failure"}, "reason": "Controlled demo recovery"}).json()
    action_id = action["action_id"]
    assert action["status"] == "pending_approval"
    edited = client.post(f"/actions/{action_id}/edit", json={"parameters": {"mode": "recovery"}}).json()
    assert edited["validation"]["valid"] and edited["approval"] is None
    assert edited["change_proposal"]["before"] == {"mode": "failure"}
    assert edited["change_proposal"]["after"] == {"mode": "recovery"}
    assert client.post(f"/actions/{action_id}/execute").status_code == 403
    assert adapter.calls == []
    assert client.post(f"/actions/{action_id}/approve").json()["status"] == "approved"
    completed = client.post(f"/actions/{action_id}/execute").json()
    assert completed["action"]["status"] == "succeeded"
    assert completed["result"]["verification"]["status"] == "verified"
    assert adapter.calls == [{"dag_id": DAG, "conf": {"mode": "recovery"}}]
    feedback = client.post(f"/actions/{action_id}/feedback", json={"useful": True, "change_quality": "correct", "comment": "Verified recovery"})
    assert feedback.status_code == 200
    assert feedback.json()["action_id"] == action_id
    assert len(adapter.calls) == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_source_proposal_cannot_enter_execution(demo_backend):
    from backend.app.change_review import build_source_code_change_proposal
    client, source, adapter = demo_backend
    action = client.post("/actions", json={"action_type": "trigger_dag", "dag_id": DAG,
        "parameters": {"mode": "recovery"}, "reason": "Controlled demo"}).json()
    action_id = action["action_id"]
    client.post(f"/actions/{action_id}/approve")
    main.action_store.get(action_id).change_proposal = build_source_code_change_proposal(
        DAG, "dags/demo.py", source.read_text(), source.read_text(), "Review only",
    )
    assert client.post(f"/actions/{action_id}/execute").status_code == 403
    assert adapter.calls == []
