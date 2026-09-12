from unittest.mock import Mock

import pytest

from backend.app.action_models import ActionRequest
from backend.app.actions.airflow import AirflowActionExecutor


DAG_ID = "support_intelligence_recoverable_failure"


def make_trigger_action(parameters=None):
    return ActionRequest(
        action_type="trigger_dag",
        dag_id=DAG_ID,
        parameters=parameters or {},
        reason="Test DAG trigger.",
        source="test",
    )


def test_trigger_dag_is_supported():
    adapter = Mock()
    executor = AirflowActionExecutor(adapter=adapter)

    action = make_trigger_action()

    assert executor.supports(action) is True


def test_trigger_dag_calls_airflow_adapter():
    adapter = Mock()

    adapter.trigger_dag.return_value = {
        "dag_run_id": "test-run-123",
        "state": "queued",
        "triggered_by": "test",
    }

    executor = AirflowActionExecutor(adapter=adapter)

    action = make_trigger_action(
        parameters={
            "mode": "recovery",
        }
    )

    result = executor.execute(action)

    adapter.trigger_dag.assert_called_once_with(
        dag_id=DAG_ID,
        logical_date=None,
        conf={
            "mode": "recovery",
        },
    )

    assert result["status"] == "submitted"
    assert result["action"] == "trigger_dag"
    assert result["dag_id"] == DAG_ID
    assert result["dag_run_id"] == "test-run-123"
    assert result["airflow_state"] == "queued"


def test_trigger_dag_supports_explicit_conf():
    adapter = Mock()

    adapter.trigger_dag.return_value = {
        "dag_run_id": "test-run-456",
        "state": "queued",
        "triggered_by": "test",
    }

    executor = AirflowActionExecutor(adapter=adapter)

    action = make_trigger_action(
        parameters={
            "conf": {
                "mode": "recovery",
            }
        }
    )

    result = executor.execute(action)

    adapter.trigger_dag.assert_called_once_with(
        dag_id=DAG_ID,
        logical_date=None,
        conf={
            "mode": "recovery",
        },
    )

    assert result["dag_run_id"] == "test-run-456"


def test_unsupported_action_is_rejected():
    adapter = Mock()
    executor = AirflowActionExecutor(adapter=adapter)

    action = make_trigger_action()

    # Force an invalid action type at runtime to verify
    # the executor's defensive check.
    action.action_type = "unsupported_action"

    with pytest.raises(AttributeError):
        executor.execute(action)


def test_retry_execution_is_not_enabled():
    adapter = Mock()
    executor = AirflowActionExecutor(adapter=adapter)

    action = ActionRequest(
        action_type="retry_failed_task",
        dag_id=DAG_ID,
        task_id="recoverable_task",
        parameters={},
        reason="Test retry.",
        source="test",
    )

    with pytest.raises(NotImplementedError, match="not enabled yet"):
        executor.execute(action)