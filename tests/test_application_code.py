"""Application taxonomy uses observed task evidence, never DAG names or operator alone."""
import pytest
from fastapi.testclient import TestClient

from backend.app.evidence_signals import extract_evidence_signals
from backend.app.hybrid_analyzer import analyze_hybrid


def runtime_evidence(exception="ZeroDivisionError", message="float division by zero"):
    return {"latest_dag_run_state": "failed", "failed_task_count": 1,
            "failed_task_id": "calculate_order_metrics", "failed_task_operator": "PythonOperator",
            "failure_exception_type": exception, "failure_exception_message": message}


@pytest.mark.parametrize("exception,message", [
    ("ZeroDivisionError", "float division by zero"),
    ("TypeError", "unsupported operand type(s) for +: float and NoneType"),
    ("KeyError", "amount"), ("AttributeError", "NoneType has no attribute total"),
    ("IndexError", "list index out of range"), ("NameError", "total is not defined"),
    ("UnboundLocalError", "local variable total referenced before assignment"),
    ("ValueError", "invalid literal for int() with base 10: 'x'"),
    ("ValueError", "could not convert string to float: 'x'"),
    ("ValueError", "not enough values to unpack (expected 2, got 1)"),
])
def test_runtime_application_exception(exception, message):
    result = extract_evidence_signals(runtime_evidence(exception, message))
    assert result.incident_class == "Application Code"
    assert result.confidence == 0.90
    assert f"Runtime exception: {exception}" in result.supporting_evidence
    assert f"Exception message: {message}" in result.supporting_evidence
    assert "Failed task: calculate_order_metrics" in result.supporting_evidence
    assert "Failed task operator: PythonOperator" in result.supporting_evidence


@pytest.mark.parametrize("exception,message,expected", [
    ("ValueError", "required service endpoint is missing", "Configuration"),
    ("ValueError", "timeout configuration is invalid", "Configuration"),
    ("KeyError", "missing environment configuration", "Configuration"),
    ("SyntaxError", "Broken DAG: invalid syntax", "DAG Parsing"),
    ("ImportError", "failed to import DAG", "DAG Parsing"),
    ("TypeError", "CrashLoopBackOff with TypeError in logs", "Kubernetes"),
    ("TypeError", "out of memory: OOM", "Resource"),
    ("TypeError", "scheduler heartbeat unavailable", "Scheduler"),
    ("ValueError", "invalid value", "Unknown"),
    ("RuntimeError", "task failed", "Unknown"),
])
def test_domain_precedence_and_ambiguous_value_error(exception, message, expected):
    assert extract_evidence_signals(runtime_evidence(exception, message)).incident_class == expected


def test_structured_kubernetes_beats_application():
    result = extract_evidence_signals(runtime_evidence("TypeError", "NoneType"), {"pod_status": "CrashLoopBackOff"})
    assert result.incident_class == "Kubernetes"


def test_direct_import_evidence_beats_other_signal():
    evidence = {**runtime_evidence("SyntaxError", "invalid syntax"), "import_error_filename": "/dags/demo.py"}
    assert extract_evidence_signals(evidence, {"pod_status": "CrashLoopBackOff"}).incident_class == "DAG Parsing"


@pytest.mark.parametrize("evidence", [{}, {"failed_task_operator": "PythonOperator"},
    {"failure_exception_type": "ZeroDivisionError", "failure_exception_message": "float division by zero"},
    {**runtime_evidence(), "failed_task_id": None},
    {**runtime_evidence(), "latest_dag_run_state": "success", "failed_task_count": 0},
    {**runtime_evidence(), "failure_exception_type": None}])
def test_insufficient_runtime_context_stays_unknown(evidence):
    assert extract_evidence_signals(evidence).incident_class == "Unknown"


@pytest.mark.parametrize("llm_status", ["not_configured", "provider_unavailable", "success"])
def test_existing_hybrid_fallback_preserves_attribution(monkeypatch, llm_status):
    monkeypatch.setattr("backend.app.hybrid_analyzer.analyze_with_llm", lambda **kw: {
        "status": llm_status, "incident_class": "Unknown", "confidence": None})
    ml = {"status": "insufficient_features", "incident_class": "Unknown", "confidence": None}
    result = analyze_hybrid(runtime_evidence(), ml)
    assert result["final_class"] == "Application Code"
    assert result["decision_mode"] == "EVIDENCE_SIGNAL_FALLBACK"
    assert result["human_review"] is True
    assert result["ml"] == ml and result["llm"]["incident_class"] == "Unknown"
    assert result["evidence_signals"]["supporting_evidence"]


def test_api_and_copilot_investigate_without_enabling_source_writes(tmp_path, monkeypatch):
    from backend.app import main, developer_copilot, source_resolver
    from backend.app.evidence import AirflowEvidence
    from backend.app.incident_evidence import IncidentEvidence
    from backend.app.source_validation import resolve_writable_demo
    monkeypatch.setenv("LLM_PROVIDER", "none")
    dag_id = "support_intelligence_order_metrics_demo"
    source = tmp_path / f"{dag_id}.py"
    source.write_text("def calculate_order_metrics():\n    return 1.0 / 0\n", encoding="utf-8")
    original = source.read_bytes()
    monkeypatch.setattr(source_resolver, "DAG_SOURCE_ROOT", tmp_path)

    class Adapter:
        def get_incident_evidence(self, dag_id):
            return IncidentEvidence(airflow=AirflowEvidence(**runtime_evidence()), kubernetes=None)
        def get_incident_timeline_data(self, dag_id):
            return {"dag_run": {"dag_id": dag_id, "dag_run_id": "existing-failed-run", "state": "failed"},
                    "task_instances": [], "task_logs": []}
    monkeypatch.setattr(main, "AirflowAdapter", Adapter)
    monkeypatch.setattr(developer_copilot, "AirflowAdapter", Adapter)
    client = TestClient(main.app)
    response = client.post(f"/analyze-airflow?dag_id={dag_id}")
    assert response.status_code == 200
    result = response.json()
    assert result["incident"]["class"] == "Application Code"
    assert result["incident"]["decision_mode"] == "EVIDENCE_SIGNAL_FALLBACK"
    assert result["ml"]["status"] == "insufficient_features"
    assert result["guidance"]["runbook"] == "application_code.md"
    assert result["guidance"]["runbook_status"] == "success"
    assert any("stack trace" in check for check in result["guidance"]["l1_checks"])
    assert result["evidence_signals"]["supporting_evidence"]
    assert not result["remediation_recommendation"]["available"]
    assert result["remediation_recommendation"]["action_type"] is None
    assert "mode" not in result["remediation_recommendation"]["reason"]
    copilot = client.post("/developer/chat", json={"dag_id": dag_id, "message": "Investigate the failed input condition"}).json()
    assert copilot["diagnosis"]["incident_class"] == "Application Code"
    assert "runtime condition" in copilot["recommended_fix"]
    assert any("edge-case" in test for test in copilot["tests_to_run"])
    assert not copilot["code_change"]["available"]
    assert copilot["code_change"]["source_remediation_id"] is None
    assert copilot["code_change"]["before_code"].encode() == original
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match="allowlisted"):
        resolve_writable_demo(dag_id)


def test_llm_taxonomy_includes_application_code():
    from backend.app.llm_analyzer import IncidentLLMResult, build_llm_prompt
    result = IncidentLLMResult(incident_class="Application Code", confidence=0.9, reasoning="runtime exception",
                              supporting_evidence=[], l1_checks=[], escalation_needed=True, escalation_reason="Review")
    assert result.incident_class == "Application Code"
    assert "Application Code" in build_llm_prompt(runtime_evidence())
