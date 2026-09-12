from backend.app.action_models import ActionRequest
from backend.app.action_validator import validate_action


DAG_ID = "support_intelligence_recoverable_failure"
TASK_ID = "recoverable_task"


def test_l1_can_validate_low_risk_retry_action():
    action = ActionRequest(
        action_type="retry_failed_task",
        dag_id=DAG_ID,
        task_id=TASK_ID,
        parameters={},
        reason="Retry failed task after investigation.",
        source="test",
    )

    result = validate_action(
        action=action,
        user_role="L1",
        available_dags={DAG_ID},
        available_tasks={
            DAG_ID: {TASK_ID},
        },
    )

    assert result.valid is True
    assert result.risk_level.value == "low"
    assert result.required_role.value == "L1"
    assert result.approval_required is True


def test_l1_cannot_validate_medium_risk_pause_action():
    action = ActionRequest(
        action_type="pause_dag",
        dag_id=DAG_ID,
        parameters={},
        reason="Pause DAG for investigation.",
        source="test",
    )

    result = validate_action(
        action=action,
        user_role="L1",
        available_dags={DAG_ID},
    )

    assert result.valid is False
    assert any(
        "not authorized" in error.lower()
        for error in result.errors
    )


def test_l2_can_validate_medium_risk_pause_action():
    action = ActionRequest(
        action_type="pause_dag",
        dag_id=DAG_ID,
        parameters={},
        reason="Pause DAG for investigation.",
        source="test",
    )

    result = validate_action(
        action=action,
        user_role="L2",
        available_dags={DAG_ID},
    )

    assert result.valid is True
    assert result.risk_level.value == "medium"
    assert result.required_role.value == "L2"
    assert result.approval_required is True


def test_unknown_dag_is_rejected():
    action = ActionRequest(
        action_type="trigger_dag",
        dag_id="does_not_exist",
        parameters={},
        reason="Test invalid DAG.",
        source="test",
    )

    result = validate_action(
        action=action,
        user_role="L1",
        available_dags={DAG_ID},
    )

    assert result.valid is False
    assert any(
        "was not found" in error.lower()
        for error in result.errors
    )