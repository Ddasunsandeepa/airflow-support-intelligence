"""Keep API regression tests away from the engineer's persisted action history."""

import pytest


@pytest.fixture(autouse=True)
def isolated_stores(tmp_path, monkeypatch):
    from backend.app import action_store, main
    from backend.app.feedback_store import FeedbackStore

    monkeypatch.setattr(action_store, "STORE_PATH", tmp_path / "actions.json")
    monkeypatch.setattr(main, "action_store", action_store.ActionStore())
    monkeypatch.setattr(main, "feedback_store", FeedbackStore(tmp_path / "feedback.json"))
