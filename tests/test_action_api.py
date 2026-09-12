from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.app.action_models import (
    ActionApproval,
    ActionRequest,
    ActionStatus,
    ApprovalDecision,
    RequiredRole,
)
from backend.app.main import app
from backend.app import main


client = TestClient(app)

DAG_ID = "support_intelligence_recoverable_failure"


def make_action_request():
    return {
        "action_type": "trigger_dag",
        "dag_id": DAG_ID,
        "parameters": {
            "mode": "recovery",
        },
        "reason": "Test controlled recovery.",
        "source": "test",
    }


def test_create_action_api_validates_and_stores_action(monkeypatch):
    catalog = {
        "dags": [
            {
                "dag_id": DAG_ID,
            }
        ]
    }

    monkeypatch.setattr(
        main.AirflowAdapter,
        "get_catalog",
        lambda self: catalog,
    )

    response = client.post(
        "/actions",
        params={
            "user_role": "L1",
            "created_by": "test-user",
        },
        json=make_action_request(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["request"]["action_type"] == "trigger_dag"
    assert body["request"]["dag_id"] == DAG_ID
    assert body["created_by"] == "test-user"
    assert body["status"] == "pending_approval"
    assert body["validation"]["valid"] is True


def test_create_action_rejects_unknown_dag(monkeypatch):
    catalog = {
        "dags": [
            {
                "dag_id": DAG_ID,
            }
        ]
    }

    monkeypatch.setattr(
        main.AirflowAdapter,
        "get_catalog",
        lambda self: catalog,
    )

    response = client.post(
        "/actions",
        params={
            "user_role": "L1",
            "created_by": "test-user",
        },
        json={
            **make_action_request(),
            "dag_id": "does_not_exist",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "proposed"
    assert body["validation"]["valid"] is False
    assert any(
        "was not found" in error.lower()
        for error in body["validation"]["errors"]
    )


def test_approve_action_api_moves_action_to_approved(monkeypatch):
    catalog = {
        "dags": [
            {
                "dag_id": DAG_ID,
            }
        ]
    }

    monkeypatch.setattr(
        main.AirflowAdapter,
        "get_catalog",
        lambda self: catalog,
    )

    create_response = client.post(
        "/actions",
        params={
            "user_role": "L1",
            "created_by": "test-user",
        },
        json=make_action_request(),
    )

    assert create_response.status_code == 200

    action_id = create_response.json()["action_id"]

    response = client.post(
        f"/actions/{action_id}/approve",
        params={
            "approved_by": "test-approver",
            "approver_role": "L1",
            "comment": "Approved for test.",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "approved"
    assert body["approval"]["decision"] == "approved"
    assert body["approval"]["approved_by"] == "test-approver"
    assert body["approval"]["approver_role"] == "L1"


def test_execute_without_approval_is_blocked(monkeypatch):
    catalog = {
        "dags": [
            {
                "dag_id": DAG_ID,
            }
        ]
    }

    monkeypatch.setattr(
        main.AirflowAdapter,
        "get_catalog",
        lambda self: catalog,
    )

    create_response = client.post(
        "/actions",
        params={
            "user_role": "L1",
            "created_by": "test-user",
        },
        json=make_action_request(),
    )

    assert create_response.status_code == 200

    action_id = create_response.json()["action_id"]

    response = client.post(
        f"/actions/{action_id}/execute"
    )

    assert response.status_code == 403
    assert "human approval" in response.json()["detail"].lower()


def test_get_action_returns_current_state(monkeypatch):
    catalog = {
        "dags": [
            {
                "dag_id": DAG_ID,
            }
        ]
    }

    monkeypatch.setattr(
        main.AirflowAdapter,
        "get_catalog",
        lambda self: catalog,
    )

    create_response = client.post(
        "/actions",
        params={
            "user_role": "L1",
            "created_by": "test-user",
        },
        json=make_action_request(),
    )

    action_id = create_response.json()["action_id"]

    response = client.get(
        f"/actions/{action_id}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["action_id"] == action_id
    assert body["request"]["dag_id"] == DAG_ID
    assert body["status"] == "pending_approval"


def test_missing_action_returns_404():
    response = client.get(
        "/actions/does-not-exist"
    )

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]