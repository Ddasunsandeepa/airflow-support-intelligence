"""Source writes are tested only against isolated temporary DAG roots."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import source_resolver, source_patch_generator
from backend.app.change_models import SourceRemediationState as State
from backend.app.source_validation import BASELINE, DEMO_DAG_ID, resolve_writable_demo, source_hash, get_demo_policy
from backend.app.source_remediation import SourceRemediationService
from backend.app.source_airflow import SourceAirflowVerifier
from backend.app.source_updater import DagSourceUpdater


class FakeAirflow:
    def __init__(self, path):
        self.path = path
        self.triggered = []
        self.parse_failure = False
        self.task_state = "success"
        self.parses = 0

    def _action_request(self, method, endpoint, **kwargs):
        if endpoint.endswith("/details"):
            self.parses += 1
            return {"relative_fileloc": self.path.name, "last_parsed": f"2026-10-04T12:{self.parses:02d}:00Z",
                    "latest_dag_version": {"id": "version-1"}, "has_import_errors": self.parse_failure and self.parses > 1,
                    "is_stale": False, "is_paused": False}
        if "/dagSources/" in endpoint:
            return {"content": self.path.read_bytes().decode()}
        return {"state": "success", "dag_versions": [{"id": "version-1"}]}

    def trigger_dag(self, **kwargs):
        self.triggered.append(kwargs)
        return {"dag_run_id": "corrected-run", "state": "queued"}

    def get_dag_runs(self, **kwargs):
        return {"dag_runs": [{"dag_run_id": "corrected-run", "state": "success"}]}

    def get_task_instances(self, *args):
        return {"task_instances": [{"task_id": get_demo_policy(self.path.stem)["task"], "state": self.task_state}]}


@pytest.fixture
def source_demo(tmp_path, monkeypatch):
    root = tmp_path / "dags"
    root.mkdir()
    path = root / f"{DEMO_DAG_ID}.py"
    path.write_bytes(BASELINE.read_bytes())
    monkeypatch.setattr(source_resolver, "DAG_SOURCE_ROOT", root)
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: {"status": "provider_unavailable"})
    source = path.read_bytes().decode()
    proposed, patch, provenance = source_patch_generator.propose_evidence_grounded_patch(DEMO_DAG_ID, source, {"exception_type": "TypeError"}, allow_demo_fallback=True)
    adapter = FakeAirflow(path)
    service = SourceRemediationService(adapter=adapter)
    record = service.create(source, proposed, patch, provenance, {"exception_type": "TypeError"}, dag_id=DEMO_DAG_ID)
    return service, record, path, adapter


def validated_approved(service, record):
    record = service.validate(record.proposal_id, record.revision, record.proposal_hash)
    assert record.validation.valid, record.validation.errors
    return service.approve(record.proposal_id, record.revision, record.proposal_hash, "test-engineer", "L2")


def test_full_review_edit_approval_apply_verify_feedback(source_demo):
    from backend.app.main import app
    service, record, path, adapter = source_demo
    original = path.read_bytes()
    first = record.original_proposed_source
    record = validated_approved(service, record)
    old_hash = record.proposal_hash
    edited = first.replace('record["amount"] for record in records', 'record.get("amount") for record in records')
    record = service.edit(record.proposal_id, 1, old_hash, edited, "reviewer")
    assert record.revision == 2 and record.approval is None and record.validation is None
    assert record.original_proposed_source == first
    assert len(record.revisions) == 2
    assert '+        record.get("amount")' in record.change.unified_diff
    assert path.read_bytes() == original
    with pytest.raises(ValueError):
        service.execute(record.proposal_id, 1, old_hash)
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 2, record.proposal_hash)
    assert result.state == State.SUCCEEDED
    assert path.read_bytes() == edited.encode()
    assert Path(result.backup_path).read_bytes() == original
    assert adapter.triggered[0]["conf"] == {}
    assert result.verification["source_match"]
    with pytest.raises(ValueError):
        service.execute(record.proposal_id, 2, record.proposal_hash)
    client = TestClient(app)
    response = client.post(f"/source-remediations/{record.proposal_id}/feedback", json={"useful": True, "change_quality": "correct"})
    assert response.status_code == 200
    assert service.store.get(record.proposal_id).feedback_id == response.json()["feedback_id"]
    assert len(adapter.triggered) == 1


def test_unapproved_and_stale_never_write(source_demo):
    service, record, path, adapter = source_demo
    original = path.read_bytes()
    with pytest.raises(ValueError):
        service.execute(record.proposal_id, 1, record.proposal_hash)
    assert path.read_bytes() == original
    record = validated_approved(service, record)
    changed = original + b"\n# external engineer change\n"
    path.write_bytes(changed)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.STALE_SOURCE
    assert path.read_bytes() == changed and not adapter.triggered


def test_wrong_hash_cannot_execute_approved_revision(source_demo):
    service, record, path, adapter = source_demo
    before = path.read_bytes()
    record = validated_approved(service, record)
    with pytest.raises(ValueError, match="revision changed"):
        service.execute(record.proposal_id, record.revision, "0" * 64)
    assert path.read_bytes() == before and not adapter.triggered


@pytest.mark.parametrize("edit", [
    lambda s: s + "\nimport os\n",
    lambda s: s.replace("return total", "return eval('1')"),
    lambda s: s.replace("return total", "return open('x', 'w')"),
    lambda s: s.replace("return total", "return total.__class__"),
    lambda s: s.replace('dag_id="support_intelligence_code_remediation_demo"', 'dag_id="other"'),
    lambda s: s.replace('"amount": None', '"amount": 0'),
    lambda s: s + "\ninvalid syntax !",
])
def test_invalid_drafts_cannot_approve_or_apply(source_demo, edit):
    service, record, path, adapter = source_demo
    original = path.read_bytes()
    record = service.edit(record.proposal_id, 1, record.proposal_hash, edit(record.original_proposed_source), "test")
    record = service.validate(record.proposal_id, record.revision, record.proposal_hash)
    assert record.state == State.VALIDATION_FAILED
    with pytest.raises(ValueError):
        service.approve(record.proposal_id, record.revision, record.proposal_hash, "test", "L2")
    assert path.read_bytes() == original and not adapter.triggered


@pytest.mark.parametrize("dag_id", ["../outside", "..\\outside", "D:\\outside.py", "other_dag", "/tmp/other", DEMO_DAG_ID + "/../other"])
def test_reset_helper_only_accepts_known_demo_targets(source_demo, dag_id):
    with pytest.raises(ValueError):
        resolve_writable_demo(dag_id)


def test_symlink_rejected(source_demo, monkeypatch):
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == f"{DEMO_DAG_ID}.py")
    with pytest.raises(ValueError, match="Symlink"):
        resolve_writable_demo(DEMO_DAG_ID)


def test_parse_failure_rolls_back_without_trigger(source_demo):
    service, record, path, adapter = source_demo
    original = path.read_bytes()
    adapter.parse_failure = True
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.APPLY_FAILED_ROLLED_BACK
    assert path.read_bytes() == original and not adapter.triggered
    assert State.AIRFLOW_PARSE_FAILED in [event.state for event in result.audit]


def test_task_failure_does_not_rollback_or_retry(source_demo):
    service, record, path, adapter = source_demo
    adapter.task_state = "failed"
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.VERIFICATION_FAILED
    assert path.read_bytes() == record.original_proposed_source.encode()
    assert len(adapter.triggered) == 1


def test_atomic_failure_preserves_original(source_demo, monkeypatch):
    from backend.app import source_updater
    service, record, path, adapter = source_demo
    original = path.read_bytes()
    record = validated_approved(service, record)
    # Patch only this component's replacement primitive, not JSON store replacement.
    def fail_write(*args):
        raise OSError("Simulated atomic write failure")
    monkeypatch.setattr(source_updater, "atomic_write", fail_write)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.APPLY_FAILED
    assert path.read_bytes() == original and not adapter.triggered
    assert Path(result.backup_path).read_bytes() == original


def test_reset_and_api_revision_conflict(source_demo):
    from backend.app.main import app
    service, record, path, _ = source_demo
    client = TestClient(app)
    endpoint = f"/source-remediations/{record.proposal_id}"
    version = {"revision": 1, "source_hash": record.proposal_hash}
    response = client.put(endpoint + "/source", json={**version, "proposed_source": record.original_proposed_source + "\n# reviewed\n", "edited_by": "test"})
    assert response.status_code == 200
    assert client.post(endpoint + "/approve", json={**version, "approved_by": "test", "approver_role": "L2"}).status_code == 409
    edited = response.json()
    reset = client.post(endpoint + "/reset", json={"revision": 2, "source_hash": edited["proposal_hash"]}).json()
    assert reset["revision"] == 3
    assert reset["change"]["source_code"]["proposed_code"] == record.original_proposed_source
    assert path.read_bytes() == BASELINE.read_bytes()


def test_structured_llm_gets_full_source_and_context(source_demo, monkeypatch):
    service, record, path, _ = source_demo
    from backend.app.source_change_provider import _replace_function_source
    import ast
    tree = ast.parse(record.original_proposed_source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    response = {"status": "success", "target_function": "summarize_transactions", "summary": "Filter missing amounts",
                "reasoning": "TypeError on None", "proposed_function": ast.get_source_segment(record.original_proposed_source, function),
                "tests_to_run": ["total 200"]}
    context = {"developer_request": "fix it", "timeline": {"dag_run": {"dag_run_id": "failed-1"}}, "exception_type": "TypeError", "task_logs": ["NoneType"]}
    def llm(prompt, model, **kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        assert payload["current_source"] == path.read_bytes().decode()
        assert payload["incident_context"] == context
        return {"status": "success", "result": {
            "status": "proposal", "diagnosis": "Task fails on missing amount", "root_cause": "None in numeric sum",
            "reasoning": response["reasoning"], "evidence_used": ["TypeError", "actual source"],
            "target_function": response["target_function"], "proposed_function": response["proposed_function"],
            "change_summary": response["summary"], "tests_to_run": response["tests_to_run"], "risks": [], "assumptions": []}}
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", llm)
    result = source_patch_generator.propose_evidence_grounded_patch(DEMO_DAG_ID, path.read_bytes().decode(), context, allow_demo_fallback=True)
    assert result[2] == "developer_llm"


@pytest.mark.parametrize("response", [{"status": "success"}, {"status": "provider_unavailable"},
    {"status": "success", "target_function": "summarize_transactions", "summary": "bad", "reasoning": "bad",
     "proposed_function": "def summarize_transactions(:", "tests_to_run": []}])
def test_bad_llm_falls_back_honestly(source_demo, monkeypatch, response):
    _, _, path, _ = source_demo
    monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw: response)
    result = source_patch_generator.propose_evidence_grounded_patch(DEMO_DAG_ID, path.read_bytes().decode(), {}, allow_demo_fallback=True)
    assert result[2] == "controlled_demo_fallback"
    assert source_patch_generator.propose_evidence_grounded_patch("unknown", path.read_bytes().decode(), {}, allow_demo_fallback=True) is None


def test_recognition_requires_matching_source_and_new_parse(source_demo, monkeypatch):
    service, record, _, adapter = source_demo
    verifier = SourceAirflowVerifier(adapter, attempts=1, poll_interval=0)
    previous = verifier.snapshot(DEMO_DAG_ID)
    with pytest.raises(ValueError, match="did not confirm"):
        verifier.wait_for_source(record, previous)


def test_direct_updater_rejects_arbitrary_path_or_old_approval(source_demo):
    service, record, path, _ = source_demo
    record = validated_approved(service, record)
    record.change.source_code.file_path = "D:/outside.py"
    with pytest.raises(ValueError, match="target"):
        service.updater.check(record)
    record.change.source_code.file_path = f"dags/{DEMO_DAG_ID}.py"
    record.approval.revision = 99
    with pytest.raises(ValueError, match="exact reviewed"):
        service.updater.check(record)


def test_parse_failure_does_not_overwrite_external_edit(source_demo, monkeypatch):
    service, record, path, adapter = source_demo
    external = b"# Another engineer's newer file\n"
    def concurrent_edit(*args):
        path.write_bytes(external)
        raise ValueError("Parse failed during concurrent edit")
    monkeypatch.setattr(SourceAirflowVerifier, "wait_for_source", concurrent_edit)
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.AIRFLOW_PARSE_FAILED
    assert path.read_bytes() == external and not adapter.triggered
    assert "Rollback could not complete" in result.audit[-1].message


def test_trigger_failure_is_not_retried_or_rolled_back(source_demo, monkeypatch):
    service, record, path, adapter = source_demo
    calls = []
    def uncertain_trigger(**kwargs):
        calls.append(kwargs)
        raise TimeoutError("Response lost")
    monkeypatch.setattr(adapter, "trigger_dag", uncertain_trigger)
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, 1, record.proposal_hash)
    assert result.state == State.EXECUTION_FAILED
    assert path.read_bytes() == record.original_proposed_source.encode()
    assert len(calls) == 1


def test_disabled_policy_and_l1_approval_blocked(source_demo, monkeypatch):
    from backend.app.action_registry import ACTION_POLICIES
    from backend.app.action_models import ActionType
    service, record, path, adapter = source_demo
    original = path.read_bytes()
    record = service.validate(record.proposal_id, 1, record.proposal_hash)
    with pytest.raises(ValueError, match="L2"):
        service.approve(record.proposal_id, 1, record.proposal_hash, "test", "L1")
    record = service.approve(record.proposal_id, 1, record.proposal_hash, "test", "L2")
    monkeypatch.setattr(ACTION_POLICIES[ActionType.TRIGGER_DAG], "enabled", False)
    with pytest.raises(ValueError, match="disabled"):
        service.execute(record.proposal_id, 1, record.proposal_hash)
    assert path.read_bytes() == original and not adapter.triggered


def test_active_other_remediation_blocks_concurrent_execute(source_demo):
    service, record, path, adapter = source_demo
    record = validated_approved(service, record)
    from uuid import uuid4
    other = record.model_copy(deep=True)
    other.proposal_id = str(uuid4())
    other.state = State.AIRFLOW_VALIDATING
    service.store.save(other)
    with pytest.raises(ValueError, match="active or interrupted"):
        service.execute(record.proposal_id, 1, record.proposal_hash)
    assert path.read_bytes() == BASELINE.read_bytes() and not adapter.triggered


def test_store_corruption_never_overwritten(source_demo):
    service, record, _, _ = source_demo
    service.store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        service.store.save(record)
    assert service.store.path.read_text() == "{broken"
