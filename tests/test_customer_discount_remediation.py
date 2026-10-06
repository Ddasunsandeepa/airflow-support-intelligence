"""Second finite demo policy; source-write tests use temporary DAG roots only."""
import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import source_resolver, source_patch_generator
from backend.app.source_validation import (
    CUSTOMER_DAG_ID, DEMO_DAG_ID, DEMO_POLICIES, demo_baseline,
    validate_structure, resolve_writable_demo,
)
from backend.app.source_remediation import SourceRemediationService
from backend.app.change_models import SourceRemediationState as State
from test_source_remediation import FakeAirflow, validated_approved


@pytest.fixture
def customer_demo(tmp_path, monkeypatch):
    root = tmp_path / "dags"
    root.mkdir()
    path = root / f"{CUSTOMER_DAG_ID}.py"
    path.write_bytes(demo_baseline(CUSTOMER_DAG_ID).read_bytes())
    monkeypatch.setattr(source_resolver, "DAG_SOURCE_ROOT", root)
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: {"status": "provider_unavailable"})
    source = path.read_bytes().decode()
    context = {"developer_request": "Fix missing tier normalization", "incident_class": "Application Code",
               "airflow_evidence": {"failure_exception_type": "AttributeError", "failure_exception_message": "'NoneType' object has no attribute 'lower'",
                                    "failed_task_id": "calculate_customer_discounts", "failed_task_operator": "PythonOperator"},
               "timeline": {"dag_run": {"dag_run_id": "existing-failure"}, "task_logs": ["AttributeError"]}}
    proposed, patch, provenance = source_patch_generator.propose_evidence_grounded_patch(CUSTOMER_DAG_ID, source, context, allow_demo_fallback=True)
    adapter = FakeAirflow(path)
    service = SourceRemediationService(adapter=adapter)
    record = service.create(source, proposed, patch, provenance, context, dag_id=CUSTOMER_DAG_ID)
    return service, record, path, adapter


def test_finite_reset_fixture_registry_and_readonly_source(customer_demo):
    _, record, path, _ = customer_demo
    assert set(DEMO_POLICIES) == {DEMO_DAG_ID, CUSTOMER_DAG_ID}
    assert resolve_writable_demo(CUSTOMER_DAG_ID) == path
    assert source_resolver.read_dag_source(CUSTOMER_DAG_ID) == record.change.source_code.before_code
    for dag_id in ("support_intelligence_order_metrics_demo", "other", "../outside", "D:/outside", "..\\outside"):
        with pytest.raises(ValueError):
            resolve_writable_demo(dag_id)


def test_fallback_fixture_and_business_results(customer_demo, capsys):
    _, record, path, _ = customer_demo
    assert record.change.source_code.generated_by == "controlled_demo_fallback"
    assert '"tier": None' in record.original_proposed_source
    # Execute only this known deterministic test function, never the DAG/imports
    # or provider output. Production validation remains compile/AST-only.
    def function_from(source):
        return next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef))
    original_function = function_from(record.change.source_code.before_code)
    corrected_function = function_from(record.original_proposed_source)
    assert ast.dump(original_function.body[1]) == ast.dump(corrected_function.body[1])
    namespace = {}
    exec(compile(ast.Module(body=[original_function], type_ignores=[]), "<known-demo-test>", "exec"), namespace)
    with pytest.raises(AttributeError, match="lower"):
        namespace[record.target_function]()
    exec(compile(ast.Module(body=[corrected_function], type_ignores=[]), "<known-fallback-test>", "exec"), namespace)
    results = namespace[record.target_function]()
    assert [(r["customer_id"], r["final_total"]) for r in results] == [("CUST-1001", 400.0), ("CUST-1002", 270.0), ("CUST-1003", 250.0)]
    assert "ProcessedCustomers=3" in capsys.readouterr().out
    assert path.read_bytes() == demo_baseline(CUSTOMER_DAG_ID).read_bytes()


def test_structured_llm_receives_actual_customer_context(customer_demo, monkeypatch):
    _, record, _, _ = customer_demo
    source = record.change.source_code.before_code
    function = next(n for n in ast.parse(record.original_proposed_source).body if isinstance(n, ast.FunctionDef))
    def llm(prompt, model, **kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        assert payload["current_source"] == source
        assert payload["incident_context"] == record.evidence
        assert payload["source_region"]["mapped_target_function"] == record.target_function
        return {"status": "success", "result": {"status": "proposal", "diagnosis": "Task failed", "root_cause": "None tier",
                "evidence_used": ["Actual AttributeError and source"], "risks": [], "assumptions": [],
                "target_function": record.target_function, "change_summary": "Normalize valid tiers",
                "reasoning": "Actual task raises AttributeError on None tier", "tests_to_run": ["Verify all three results"],
                "proposed_function": ast.get_source_segment(record.original_proposed_source, function)}}
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", llm)
    result = source_patch_generator.propose_evidence_grounded_patch(CUSTOMER_DAG_ID, source, record.evidence, allow_demo_fallback=True)
    assert result[2] == "developer_llm"


@pytest.mark.parametrize("response", [{"status": "success"}, {"status": "invalid_llm_response"},
    {"status": "success", "target_function": "calculate_customer_discounts", "summary": "bad", "reasoning": "bad",
     "tests_to_run": [], "proposed_function": "def calculate_customer_discounts(:"}])
def test_invalid_provider_output_falls_back_honestly(customer_demo, monkeypatch, response):
    _, record, _, _ = customer_demo
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: response)
    result = source_patch_generator.propose_evidence_grounded_patch(CUSTOMER_DAG_ID, record.change.source_code.before_code, record.evidence, allow_demo_fallback=True)
    assert result[2] == "controlled_demo_fallback"


def test_review_edit_execute_backup_verify_feedback(customer_demo):
    from backend.app.main import app
    service, record, path, adapter = customer_demo
    original = path.read_bytes()
    with pytest.raises(ValueError):
        service.execute(record.proposal_id, 1, record.proposal_hash)
    record = validated_approved(service, record)
    old_hash = record.proposal_hash
    edited = record.original_proposed_source.replace('else ""', 'else "standard"')
    record = service.edit(record.proposal_id, 1, old_hash, edited, "test-engineer")
    assert record.revision == 2 and record.validation is None and record.approval is None
    assert record.original_proposed_source != edited and len(record.revisions) == 2
    assert 'else "standard"' in record.change.unified_diff
    with pytest.raises(ValueError):
        service.execute(record.proposal_id, 1, old_hash)
    assert path.read_bytes() == original
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 2, record.proposal_hash)
    assert result.state == State.SUCCEEDED
    assert path.read_bytes() == edited.encode()
    assert Path(result.backup_path).read_bytes() == original
    assert adapter.triggered[0]["conf"] == {}
    assert result.verification["source_match"]
    assert result.verification["task_states"][0]["task_id"] == "calculate_customer_discounts"
    assert TestClient(app).post(f"/source-remediations/{record.proposal_id}/feedback", json={"useful": True, "change_quality": "correct"}).status_code == 200
    with pytest.raises(ValueError):
        service.execute(record.proposal_id, 2, record.proposal_hash)
    assert len(adapter.triggered) == 1


@pytest.mark.parametrize("change", [
    lambda s: s.replace('"tier": None', '"tier": "gold"'),
    lambda s: s.replace(CUSTOMER_DAG_ID, "arbitrary_dag"),
    lambda s: s.replace('task_id="calculate_customer_discounts"', 'task_id="other"'),
    lambda s: s.replace("def calculate_customer_discounts():", "def other():"),
    lambda s: s.replace("return processed_customers", "return open('x')"),
    lambda s: s + "\nimport os\n",
    lambda s: s + "\ninvalid ! syntax",
])
def test_invalid_review_cannot_apply(customer_demo, change):
    service, record, path, adapter = customer_demo
    original = path.read_bytes()
    record = service.edit(record.proposal_id, 1, record.proposal_hash, change(record.original_proposed_source), "test")
    record = service.validate(record.proposal_id, 2, record.proposal_hash)
    assert not record.validation.valid
    with pytest.raises(ValueError):
        service.approve(record.proposal_id, 2, record.proposal_hash, "test", "L2")
    assert path.read_bytes() == original and not adapter.triggered


def test_customer_stale_source_and_parse_rollback(customer_demo):
    service, record, path, adapter = customer_demo
    original = path.read_bytes()
    record = validated_approved(service, record)
    path.write_bytes(original + b"\n# external change\n")
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.STALE_SOURCE and not adapter.triggered


def test_customer_parse_failure_rolls_back(customer_demo):
    service, record, path, adapter = customer_demo
    original = path.read_bytes()
    adapter.parse_failure = True
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.APPLY_FAILED_ROLLED_BACK
    assert path.read_bytes() == original and not adapter.triggered


def test_customer_wrong_task_fails_verification_without_retry(customer_demo, monkeypatch):
    service, record, path, adapter = customer_demo
    monkeypatch.setattr(adapter, "get_task_instances", lambda *args: {"task_instances": [{"task_id": "summarize_transactions", "state": "success"}]})
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.VERIFICATION_FAILED
    assert path.read_bytes() == record.original_proposed_source.encode()
    assert len(adapter.triggered) == 1


def test_reset_only_customer_demo(customer_demo, tmp_path, monkeypatch):
    from scripts import reset_code_remediation_demo as reset
    _, record, path, _ = customer_demo
    other = path.parent / f"{DEMO_DAG_ID}.py"
    other.write_bytes(b"# do not reset this demo\n")
    path.write_bytes(record.original_proposed_source.encode())
    # Reset backup storage also stays in the temporary test tree.
    monkeypatch.setattr(reset, "BASELINE", tmp_path / "demo_dags" / "baseline.py")
    reset.reset_demo(CUSTOMER_DAG_ID)
    assert path.read_bytes() == demo_baseline(CUSTOMER_DAG_ID).read_bytes()
    assert other.read_bytes() == b"# do not reset this demo\n"
    backups = list((tmp_path / "data" / "source_backups").glob("*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == record.original_proposed_source.encode()
    with pytest.raises(ValueError):
        reset.reset_demo("../../other")


def test_original_policy_does_not_gain_customer_methods():
    source = demo_baseline(DEMO_DAG_ID).read_text()
    with pytest.raises(ValueError):
        validate_structure(source, source.replace("return total", "return 'gold'.lower()"), DEMO_DAG_ID)
