import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.action_models import ActionRequest, ActionStatus, RemediationAction
from backend.app.feedback_models import RemediationFeedback
from backend.app.feedback_store import FeedbackStore


@pytest.fixture
def action():
    item = RemediationAction(
        request=ActionRequest(action_type="trigger_dag", dag_id="demo", reason="Test"),
        created_by="engineer", status=ActionStatus.SUCCEEDED,
    )
    main.action_store.save(item)
    return item


@pytest.mark.parametrize("status", [ActionStatus.SUCCEEDED, ActionStatus.FAILED])
@pytest.mark.parametrize("useful", [True, False])
@pytest.mark.parametrize("quality", ["correct", "partially_correct", "incorrect"])
def test_feedback_persists_without_execution(action, monkeypatch, status, useful, quality):
    action.status = status
    main.action_store.save(action)
    before = action.model_dump(mode="json")
    execute = Mock(side_effect=AssertionError("Feedback must never execute"))
    monkeypatch.setattr(main.action_service, "execute", execute)
    client = TestClient(main.app)
    response = client.post(f"/actions/{action.action_id}/feedback", json={"useful": useful, "change_quality": quality})
    assert response.status_code == 200
    result = response.json()
    assert result["action_id"] == action.action_id
    assert result["useful"] is useful
    assert result["change_quality"] == quality
    assert result["comment"] is None
    assert result["feedback_id"] and result["created_at"]
    assert action.model_dump(mode="json") == before
    execute.assert_not_called()
    # Re-open from disk, not an in-memory cache.
    assert FeedbackStore(main.feedback_store.path).get_for_action(action.action_id).feedback_id == result["feedback_id"]
    assert client.get(f"/actions/{action.action_id}/feedback").json() == result


def test_feedback_comment_retry_and_existing_records(action):
    client = TestClient(main.app)
    original = RemediationFeedback(action_id="another-action", useful=False, change_quality="incorrect", comment="Keep me")
    main.feedback_store.save(original)
    body = {"useful": True, "change_quality": "correct", "comment": 'Helpful "review"\nNo further action.'}
    first = client.post(f"/actions/{action.action_id}/feedback", json=body)
    second = client.post(f"/actions/{action.action_id}/feedback", json={**body, "useful": False})
    assert first.json() == second.json()
    assert first.json()["comment"] == body["comment"]
    assert len(json.loads(main.feedback_store.path.read_text())) == 2
    assert main.feedback_store.get_for_action("another-action") == original


@pytest.mark.parametrize("status", [s for s in ActionStatus if s not in {ActionStatus.SUCCEEDED, ActionStatus.FAILED}])
def test_nonterminal_feedback_rejected(action, status):
    action.status = status
    response = TestClient(main.app).post(f"/actions/{action.action_id}/feedback", json={"useful": True, "change_quality": "correct"})
    assert response.status_code == 409
    assert not main.feedback_store.path.exists()


@pytest.mark.parametrize("body", [{"useful": True}, {"change_quality": "correct"}, {"useful": "false", "change_quality": "correct"}, {"useful": True, "change_quality": "excellent"}])
def test_invalid_feedback(action, body):
    assert TestClient(main.app).post(f"/actions/{action.action_id}/feedback", json=body).status_code == 422


def test_missing_action_and_empty_store():
    client = TestClient(main.app)
    assert client.post("/actions/missing/feedback", json={"useful": False, "change_quality": "incorrect"}).status_code == 404
    assert client.get("/actions/missing/feedback").status_code == 404
    assert main.feedback_store.get_for_action("missing") is None


def test_corrupt_store_preserved(action):
    main.feedback_store.path.write_text("invalid JSON", encoding="utf-8")
    response = TestClient(main.app).post(f"/actions/{action.action_id}/feedback", json={"useful": True, "change_quality": "correct"})
    assert response.status_code == 503
    assert main.feedback_store.path.read_text() == "invalid JSON"


def test_concurrent_feedback_preserves_records(tmp_path):
    path = tmp_path / "feedback.json"
    def submit(index):
        return FeedbackStore(path).save(RemediationFeedback(action_id=str(index), useful=True, change_quality="correct"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(submit, range(12)))
    assert len(json.loads(path.read_text())) == 12
