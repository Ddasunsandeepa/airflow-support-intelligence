from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import main


client = TestClient(app)

DAG_ID = "support_intelligence_recoverable_failure"


def make_action_request():
    return {
        "action_type": "trigger_dag",
        "dag_id": DAG_ID,
        "parameters": {"mode": "recovery"},
        "reason": "Controlled recovery test.",
        "source": "test",
    }


def test_full_remediation_lifecycle(monkeypatch):
    # ---------------------------------------------------------
    # 1. Provide a synthetic Airflow catalog
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 2. Create remediation action
    # ---------------------------------------------------------
    create_response = client.post(
        "/actions",
        params={
            "user_role": "L1",
            "created_by": "test-user",
        },
        json=make_action_request(),
    )

    assert create_response.status_code == 200

    created = create_response.json()

    action_id = created["action_id"]

    assert created["status"] == "pending_approval"
    assert created["validation"]["valid"] is True
    assert created["request"]["action_type"] == "trigger_dag"
    assert created["request"]["dag_id"] == DAG_ID

    # ---------------------------------------------------------
    # 3. Approve remediation action
    # ---------------------------------------------------------
    approve_response = client.post(
        f"/actions/{action_id}/approve",
        params={
            "approved_by": "test-approver",
            "approver_role": "L1",
            "comment": "Approved for controlled recovery test.",
        },
    )

    assert approve_response.status_code == 200

    approved = approve_response.json()

    assert approved["status"] == "approved"
    assert approved["approval"]["decision"] == "approved"
    assert approved["approval"]["approved_by"] == "test-approver"
    assert approved["approval"]["approver_role"] == "L1"

    # ---------------------------------------------------------
    # 4. Replace real Airflow executor with a controlled mock
    # ---------------------------------------------------------
    mock_executor = Mock()

    mock_executor.supports.return_value = True

    mock_executor.execute.return_value = {
        "status": "submitted",
        "action": "trigger_dag",
        "dag_id": DAG_ID,
        "dag_run_id": "manual__test_recovery_run",
        "airflow_state": "queued",
        "triggered_by": "test-user",
    }

    # ---------------------------------------------------------
    # 5. Mock verification as successful
    # ---------------------------------------------------------
    mock_verification = Mock()

    mock_verification.verify_dag_run.return_value = {
        "status": "verified",
        "state": "success",
        "dag_id": DAG_ID,
        "dag_run_id": "manual__test_recovery_run",
    }

    monkeypatch.setattr(
        main.action_service,
        "airflow_executor",
        mock_executor,
    )

    monkeypatch.setattr(
        main.action_service,
        "verification_engine",
        mock_verification,
    )

    # ---------------------------------------------------------
    # 6. Execute approved action
    # ---------------------------------------------------------
    execute_response = client.post(
        f"/actions/{action_id}/execute",
    )

    assert execute_response.status_code == 200

    result = execute_response.json()

    print("\nEXECUTION RESULT:")
    print(result)

    # ---------------------------------------------------------
    # 7. Verify final lifecycle state
    # ---------------------------------------------------------
    action = result["action"]

    assert action["action_id"] == action_id
    assert action["status"] == "succeeded"

    assert result["result"]["status"] == "succeeded"
    assert result["result"]["execution"]["status"] == "submitted"
    assert result["result"]["execution"]["dag_id"] == DAG_ID
    assert result["result"]["execution"]["dag_run_id"] == "manual__test_recovery_run"
    assert result["result"]["verification"]["status"] == "verified"

    # ---------------------------------------------------------
    # 8. Verify executor and verification were actually called
    # ---------------------------------------------------------
    mock_executor.supports.assert_called_once()

    mock_executor.execute.assert_called_once()

    mock_verification.verify_dag_run.assert_called_once_with(
        dag_id=DAG_ID,
        dag_run_id="manual__test_recovery_run",
    )