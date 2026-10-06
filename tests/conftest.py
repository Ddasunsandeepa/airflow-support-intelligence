"""Keep API regression tests away from the engineer's persisted action history."""

import pytest
import hashlib
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def real_dags_unchanged():
    """Read-only guard: automated tests must never mutate the real local DAGs."""
    root = Path(__file__).resolve().parents[2] / "airflow" / "dags"
    def fingerprints():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*.py")} if root.exists() else {}
    before = fingerprints()
    yield
    assert fingerprints() == before, "Automated tests changed a real Airflow DAG file!"


@pytest.fixture(autouse=True)
def isolated_stores(tmp_path, monkeypatch):
    from backend.app import action_store, main
    from backend.app.feedback_store import FeedbackStore
    from backend.app import source_remediation_store

    monkeypatch.setattr(action_store, "STORE_PATH", tmp_path / "actions.json")
    monkeypatch.setattr(main, "action_store", action_store.ActionStore())
    monkeypatch.setattr(main, "feedback_store", FeedbackStore(tmp_path / "feedback.json"))
    monkeypatch.setattr(source_remediation_store, "STORE_PATH", tmp_path / "source-remediations.json")
