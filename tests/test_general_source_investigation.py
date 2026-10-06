"""General AI proposals are reviewable independently of permission to write."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from backend.app import developer_copilot, source_patch_generator, source_resolver, main
from backend.app.ai_source_investigation import investigate_source
from backend.app.source_remediation import SourceRemediationService
from backend.app.source_review_validation import resolve_review_source
from backend.app.source_validation import DEMO_DAG_ID, demo_baseline
from backend.app.evidence import AirflowEvidence
from backend.app.incident_evidence import IncidentEvidence


def model_response(function="calculate", replacement="def calculate():\n    return 7"):
    return {"status": "success", "provider_attempts": [{"provider": "gemini", "status": "success"}],
            "result": {"status": "proposal", "diagnosis": "Observed task failure",
            "root_cause": "Input assumption contradicted by supplied source", "reasoning": "Compare exception and source",
            "evidence_used": ["Actual task exception", "Actual source"], "target_function": function,
            "proposed_function": replacement, "change_summary": "Handle the observed input condition",
            "tests_to_run": ["Check failing input and normal input"], "risks": ["Confirm business semantics"],
            "assumptions": ["Source snapshot matches the failed run"]}}


def write_source(tmp_path, monkeypatch, name="arbitrary_orders", body="return 1 / 0"):
    monkeypatch.setattr(source_resolver, "DAG_SOURCE_ROOT", tmp_path)
    path = tmp_path / f"{name}.py"
    path.write_text('from airflow import DAG\nfrom airflow.providers.standard.operators.python import PythonOperator\n'
                    f'def calculate():\n    {body}\n'
                    f'with DAG(dag_id="{name}", schedule=None) as dag:\n'
                    '    task = PythonOperator(task_id="compute", python_callable=calculate)\n', encoding="utf-8")
    return path


@pytest.mark.parametrize("dag_id,exception,body,patch", [
    ("shop_normalization", "AttributeError", "tier = None\n    return tier.lower()", "tier = None\n    return tier.lower() if tier is not None else ''"),
    ("regional_metrics", "ZeroDivisionError", "denominator = 0\n    return 10 / denominator", "denominator = 0\n    return 10 / denominator if denominator else 0"),
    ("warehouse_lookup", "KeyError", "return {}['missing']", "return {}.get('missing', 0)"),
])
def test_arbitrary_failed_dag_same_ai_review_pipeline(tmp_path, monkeypatch, dag_id, exception, body, patch):
    path = write_source(tmp_path, monkeypatch, dag_id, body)
    before = path.read_bytes()
    adapter = Mock()
    adapter.get_incident_evidence.return_value = IncidentEvidence(airflow=AirflowEvidence(
        latest_dag_run_state="failed", failed_task_count=1, failed_task_id="compute",
        failed_task_operator="PythonOperator", failure_exception_type=exception,
        failure_exception_message="Observed task input failure"), kubernetes=None)
    adapter.get_incident_timeline_data.return_value = {"dag_run": {"dag_run_id": "failed-existing", "state": "failed"},
        "task_instances": [{"task_id": "compute", "state": "failed"}], "task_logs": [exception]}
    monkeypatch.setattr(developer_copilot, "AirflowAdapter", lambda: adapter)
    monkeypatch.setattr(developer_copilot, "analyze_airflow_with_ml", lambda _: {"status": "insufficient_features"})
    monkeypatch.setattr(developer_copilot, "analyze_hybrid", lambda **kw: {"final_class": "Application Code", "final_confidence": .9})
    calls = []
    def llm(prompt, schema, **kwargs):
        context = json.loads(prompt.split("\n", 1)[1])
        calls.append(context)
        assert context["current_source"] == before.decode()
        assert context["source_region"]["mapped_target_function"] == "calculate"
        evidence = context["incident_context"]
        assert evidence["airflow_evidence"]["failure_exception_type"] == exception
        assert exception in evidence["task_log_excerpt"]
        assert evidence["timeline"]["dag_run"]["dag_run_id"] == "failed-existing"
        assert all(k in evidence for k in ("ml_result", "evidence_signals", "hybrid_analysis", "developer_request"))
        assert kwargs["diagnostics"] is True
        response = model_response(replacement=f"def calculate():\n    {patch}")
        schema.model_validate(response["result"])
        return response
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", llm)
    client = TestClient(main.app)
    response = client.post("/developer/chat", json={"message": "Investigate actual failure", "dag_id": dag_id})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(calls) == 1 and result["proposal_status"] == "developer_llm"
    assert result["root_cause"] and result["evidence_used"] and result["risks"] and result["assumptions"]
    pid = result["code_change"]["source_remediation_id"]
    record = client.get(f"/source-remediations/{pid}").json()
    assert record["execution_allowed"] is True
    assert record["change"]["additions"] and record["change"]["deletions"]
    version = {"revision": record["revision"], "source_hash": record["proposal_hash"]}
    edited = record["change"]["source_code"]["proposed_code"].replace("\r\n", "\n").replace(patch, "result = 8\n    return result")
    record = client.put(f"/source-remediations/{pid}/source", json={**version, "proposed_source": edited, "edited_by": "test"}).json()
    assert record["revision"] == 2 and record["approval"] is None and record["validation"] is None
    assert record["original_proposed_source"] != edited and len(record["revisions"]) == 2
    assert "+    result = 8" in record["change"]["unified_diff"]
    version = {"revision": 2, "source_hash": record["proposal_hash"]}
    validated = client.post(f"/source-remediations/{pid}/validate", json=version).json()
    assert validated["validation"]["valid"], validated
    approval = client.post(f"/source-remediations/{pid}/approve", json={**version, "approved_by": "test", "approver_role": "L2"})
    assert approval.status_code == 200, approval.text
    assert path.read_bytes() == before  # approval is not application
    from test_source_remediation import FakeAirflow
    class GeneralAirflow(FakeAirflow):
        def get_task_instances(self, *args):
            return {"task_instances": [{"task_id": "compute", "state": "success"},
                                       {"task_id": "downstream", "state": "success"}]}
    from backend.app import source_remediation
    fake = GeneralAirflow(path)
    monkeypatch.setattr(source_remediation, "AirflowAdapter", lambda: fake)
    executed = client.post(f"/source-remediations/{pid}/execute", json=version)
    assert executed.status_code == 200, executed.text
    completed = executed.json()
    assert completed["state"] == "succeeded", completed["audit"]
    assert path.read_bytes() == edited.encode()
    assert Path(completed["backup_path"]).read_bytes() == before
    assert len(fake.triggered) == 1
    assert client.post(f"/source-remediations/{pid}/feedback", json={"useful": True, "change_quality": "correct"}).status_code == 200
    assert client.get(f"/source-remediations/{pid}/feedback").json()["useful"] is True
    assert client.get(f"/source-remediations/{pid}").json()["state"] == "succeeded"
    adapter.trigger_dag.assert_not_called()



@pytest.mark.parametrize("opt_in", [False, True])
def test_ordinary_provider_failure_never_selects_patch(tmp_path, monkeypatch, opt_in):
    path = write_source(tmp_path, monkeypatch)
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: {"status": "provider_unavailable"})
    result = investigate_source(path.stem, path.read_text(), {}, allow_demo_fallback=opt_in)
    assert result["proposal"] is None and result["provenance"] == "no_proposal"
    assert result["provider_status"] == "provider_unavailable"


def test_demo_fallback_requires_opt_in(monkeypatch):
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: {"status": "not_configured"})
    source = demo_baseline(DEMO_DAG_ID).read_text()
    assert investigate_source(DEMO_DAG_ID, source, {})["proposal"] is None
    result = investigate_source(DEMO_DAG_ID, source, {}, allow_demo_fallback=True)
    assert result["provenance"] == result["proposal"][2] == "controlled_demo_fallback"
    assert result["provider_status"] == "not_configured"


@pytest.mark.parametrize("mutation", [
    lambda r: r["result"].update(file_path="../../outside.py"),
    lambda r: r["result"].update(proposed_function="def calculate(:"),
    lambda r: r["result"].update(target_function="wrong", proposed_function="def wrong():\n    return 7"),
    lambda r: r["result"].update(proposed_function="def calculate():\n    return 7\nimport os"),
    lambda r: r["result"].update(proposed_function="def calculate(x):\n    return 7"),
    lambda r: r["result"].pop("risks"),
])
def test_untrusted_model_output_rejected(tmp_path, monkeypatch, mutation):
    path = write_source(tmp_path, monkeypatch)
    before = path.read_bytes()
    response = model_response()
    mutation(response)
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: response)
    result = investigate_source(path.stem, path.read_text(), {"airflow_evidence": {"failed_task_id": "compute"}})
    assert result["proposal"] is None and result["provider_status"] == "invalid_source_proposal"
    assert path.read_bytes() == before


def test_model_no_proposal_is_not_replaced_by_demo_fallback(monkeypatch):
    response = model_response()
    response["result"].update(status="no_proposal", target_function=None, proposed_function=None)
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: response)
    result = investigate_source(DEMO_DAG_ID, demo_baseline(DEMO_DAG_ID).read_text(), {}, allow_demo_fallback=True)
    assert result["proposal"] is None and result["investigation"]["diagnosis"]


@pytest.mark.parametrize("link_method", ["is_symlink", "is_junction"])
def test_general_resolution_rejects_links(tmp_path, monkeypatch, link_method):
    path = write_source(tmp_path, monkeypatch)
    monkeypatch.setattr(Path, link_method, lambda self: self.name == path.name)
    with pytest.raises(ValueError, match="Symlink/junction"):
        resolve_review_source(path.stem)


@pytest.mark.parametrize("dag_id", ["../outside", "..\\outside", "D:/outside", "/outside", " arbitrary_orders", "arbitrary_orders "])
def test_general_review_rejects_noncanonical_or_outside_target(tmp_path, monkeypatch, dag_id):
    write_source(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        resolve_review_source(dag_id)


def test_general_review_stale_source_and_client_path_rejected(tmp_path, monkeypatch):
    path = write_source(tmp_path, monkeypatch)
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: model_response())
    before = path.read_bytes().decode("utf-8")
    proposed, patch, provenance = investigate_source(path.stem, before, {})["proposal"]
    service = SourceRemediationService()
    record = service.create(before, proposed, patch, provenance, {}, dag_id=path.stem)
    path.write_text(before + "\n# concurrent change\n")
    validated = service.validate(record.proposal_id, 1, record.proposal_hash)
    assert not validated.validation.valid and not validated.validation.checks["source_unchanged"]
    response = TestClient(main.app).put(f"/source-remediations/{record.proposal_id}/source", json={
        "revision": 1, "source_hash": record.proposal_hash, "proposed_source": proposed,
        "edited_by": "test", "file_path": "../../outside.py"})
    assert response.status_code == 422


def test_safe_provider_diagnostics_keep_category_without_secret(monkeypatch):
    from backend.app.developer_llm import request_structured_llm
    from backend.app.ai_source_investigation import DeveloperRemediationResponse
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    monkeypatch.delenv("LLM_FALLBACK_PROVIDERS", raising=False)
    response = requests.Response()
    response.status_code = 404
    response._content = json.dumps({"error": {"status": "NOT_FOUND", "message": "Model unavailable key=secret-test-key"}}).encode()
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    result = request_structured_llm("test", DeveloperRemediationResponse, openai_model="test", diagnostics=True)
    assert result["status"] == "provider_unavailable"
    assert result["provider_attempts"][0]["http_status"] == 404
    assert result["provider_attempts"][0]["error_category"] == "NOT_FOUND"
    assert "secret-test-key" not in json.dumps(result)
