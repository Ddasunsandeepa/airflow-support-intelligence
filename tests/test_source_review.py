import ast
from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.app import source_resolver as resolver, source_change_provider as provider, main
from backend.app.action_models import ActionRequest
from backend.app.change_review import build_runtime_change_proposal, build_source_code_change_proposal
from backend.app.source_patch_generator import generate_source_patch


DAG = "support_intelligence_configuration_review_demo"
SOURCE = '''from datetime import datetime
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

UNCHANGED = "preserve me"

def helper():
    return UNCHANGED

def configuration_review_demo(**context):
    # old controlled configuration
    raise ValueError("required service endpoint is missing")

with DAG(dag_id="support_intelligence_configuration_review_demo", schedule=None) as dag:
    task = PythonOperator(task_id="validate", python_callable=configuration_review_demo)
'''


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, "DAG_SOURCE_ROOT", tmp_path)
    path = tmp_path / f"{DAG}.py"
    path.write_text(SOURCE, encoding="utf-8", newline="")
    return path


def test_readonly_resolution_and_unknown_dag(source):
    original = source.read_bytes()
    assert resolver.resolve_dag_source(DAG) == source
    assert resolver.read_dag_source(DAG) == SOURCE
    assert resolver.get_relative_dag_path(DAG) == f"dags/{DAG}.py"
    assert resolver.resolve_dag_source("nonexistent") is None
    other = source.parent / "new_customer_dag.py"
    other.write_text("raise RuntimeError('must never execute')", encoding="utf-8")
    assert resolver.read_dag_source("new_customer_dag") == other.read_text()
    assert provider.get_controlled_source_change("new_customer_dag") is None
    assert source.read_bytes() == original


@pytest.mark.parametrize("dag_id", ["../../secret", "..\\secret", "/tmp/secret", "C:\\secret", "", "..", "bad\x00name"])
def test_traversal_rejected(source, dag_id):
    assert resolver.resolve_dag_source(dag_id) is None


def test_resolved_path_escape_rejected(source, monkeypatch):
    from pathlib import Path
    real_resolve = Path.resolve
    def resolve(path, *args, **kwargs):
        if path == source:
            return source.parent.parent / "outside.py"
        return real_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    assert resolver.resolve_dag_source(DAG) is None


def test_full_source_proposal_preserves_unaffected_code(source):
    before = source.read_bytes()
    proposal = provider.get_controlled_source_change(DAG, "Configuration", "LIVE: endpoint missing")
    assert proposal.before_code == SOURCE
    assert proposal.generated_by == "controlled_fallback"
    assert "LIVE: endpoint missing" in proposal.reason
    assert "if timeout_seconds <= 0:" in proposal.proposed_code
    ast.parse(proposal.proposed_code)
    start = SOURCE.index("def configuration_review_demo")
    end = SOURCE.index("\nwith DAG")
    assert proposal.proposed_code[:start] == SOURCE[:start]
    assert proposal.proposed_code[proposal.proposed_code.index("\nwith DAG"):] == SOURCE[end:]
    assert source.read_bytes() == before
    # Subsequent calls use current source rather than a captured snapshot.
    source.write_text(SOURCE.replace('preserve me', 'edited by engineer'), encoding="utf-8")
    assert "edited by engineer" in provider.get_controlled_source_change(DAG).before_code


@pytest.mark.parametrize("replacement", ["", "def wrong(**context):\n    pass", "def configuration_review_demo():\n    pass", "def configuration_review_demo(**context):\n    pass\nprint('extra')", "not python !", "def configuration_review_demo(**context):\n    break"])
def test_invalid_suggestion_fails_safely(source, monkeypatch, replacement):
    suggestion = replace(generate_source_patch(DAG), proposed_function=replacement)
    monkeypatch.setattr(provider, "generate_source_patch", lambda **kwargs: suggestion)
    assert provider.get_controlled_source_change(DAG) is None
    assert source.read_text() == SOURCE


def test_missing_or_invalid_source(source, monkeypatch):
    source.write_text("invalid python !", encoding="utf-8")
    assert provider.get_controlled_source_change(DAG) is None
    source.unlink()
    assert provider.get_controlled_source_change(DAG) is None
    monkeypatch.setattr(provider, "generate_source_patch", lambda **kwargs: None)
    assert provider.get_controlled_source_change(DAG) is None


def test_replacement_preserves_decorators_and_newlines():
    source = "import x\r\n\r\n@decorate\r\ndef f(**context):\r\n    return 1\r\n\r\nTAIL = True\r\n"
    proposed = provider._replace_function_source(source, "f", "def f(**context):\n    return 2")
    assert proposed == source.replace("return 1", "return 2")


def test_source_and_runtime_diffs(source):
    proposal = provider.get_controlled_source_change(DAG)
    review = build_source_code_change_proposal(
        proposal.target, proposal.file_path, proposal.before_code, proposal.proposed_code, proposal.reason,
    )
    assert review.unified_diff.startswith(f"--- dags/{DAG}.py\n+++ dags/{DAG}.py (proposed)")
    lines = review.unified_diff.splitlines()
    assert review.additions == len([line for line in lines if line.startswith('+') and not line.startswith('+++')])
    assert review.deletions == len([line for line in lines if line.startswith('-') and not line.startswith('---')])
    assert not any(line.startswith(("-from ", "-with DAG", "-    task =")) for line in lines)
    runtime = build_runtime_change_proposal(
        ActionRequest(action_type="trigger_dag", dag_id=DAG, parameters={"mode": "recovery"}, reason="Recovery"),
        previous_configuration={"mode": "failure"},
    )
    assert '-  "mode": "failure"' in runtime.unified_diff
    assert '+  "mode": "recovery"' in runtime.unified_diff
    assert runtime.additions == runtime.deletions == 1


def test_copilot_passes_evidence_and_keeps_proposal_reason(source, monkeypatch):
    from backend.app import developer_copilot as copilot
    from backend.app.evidence import AirflowEvidence
    from backend.app.incident_evidence import IncidentEvidence
    adapter = Mock()
    adapter.get_incident_evidence.return_value = IncidentEvidence(
        airflow=AirflowEvidence(failure_exception_message="LIVE missing service endpoint"), kubernetes=None,
    )
    monkeypatch.setattr(copilot, "AirflowAdapter", lambda: adapter)
    monkeypatch.setattr(copilot, "analyze_airflow_with_ml", lambda _: {})
    monkeypatch.setattr(copilot, "analyze_hybrid", lambda **kwargs: {"final_class": "Configuration", "final_confidence": .9})
    monkeypatch.setattr(copilot, "analyze_with_developer_llm", lambda **kwargs: {
        "status": "success", "summary": "Diagnosis", "reasoning": "Reasoning", "recommended_fix": "Investigate",
        "tests_to_run": [], "code_change_summary": "Generic LLM advice must not overwrite patch evidence",
    })
    result = TestClient(main.app).post("/developer/chat", json={"message": "Why?", "dag_id": DAG}).json()
    change = result["code_change"]
    assert change["available"] and "LIVE missing" in change["reason"]
    assert change["generated_by"] == "controlled_fallback"
    for target in ("unknown_dag", DAG):
        if target == DAG:
            source.unlink()
        result = TestClient(main.app).post("/developer/chat", json={"message": "Why?", "dag_id": target})
        assert result.status_code == 200
        assert result.json()["code_change"]["available"] is False
        assert "No reviewed source proposal" in result.json()["code_change"]["summary"]
