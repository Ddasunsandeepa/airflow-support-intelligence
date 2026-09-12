from unittest.mock import Mock

from backend.app.action_models import (
    ActionRequest,
    ActionStatus,
)
from backend.app.action_service import ActionService


DAG_ID = "support_intelligence_recoverable_failure"
TASK_ID = "recoverable_task"


def make_action(
    action_type="retry_failed_task",
    task_id=TASK_ID,
):
    return ActionRequest(
        action_type=action_type,
        dag_id=DAG_ID,
        task_id=task_id,
        parameters={},
        reason="Test remediation action.",
        source="test",
    )


def make_service():
    executor = Mock()
    verification_engine = Mock()

    service = ActionService(
        airflow_executor=executor,
        verification_engine=verification_engine,
    )

    return service, executor, verification_engine


def test_create_action_starts_in_proposed_state():
    service, _, _ = make_service()

    action = make_action()

    remediation = service.create_action(
        action=action,
        created_by="test-user",
    )

    assert remediation.status == ActionStatus.PROPOSED
    assert remediation.created_by == "test-user"
    assert remediation.validation is None
    assert remediation.approval is None


def test_valid_low_risk_action_moves_to_pending_approval():
    service, _, _ = make_service()

    remediation = service.create_action(
        action=make_action(),
        created_by="test-user",
    )

    service.validate(
        remediation=remediation,
        user_role="L1",
        available_dags={DAG_ID},
        available_tasks={
            DAG_ID: {TASK_ID},
        },
    )

    assert remediation.validation is not None
    assert remediation.validation.valid is True
    assert remediation.status == ActionStatus.PENDING_APPROVAL


def test_invalid_action_remains_proposed():
    service, _, _ = make_service()

    remediation = service.create_action(
        action=make_action(task_id="does_not_exist"),
        created_by="test-user",
    )

    service.validate(
        remediation=remediation,
        user_role="L1",
        available_dags={DAG_ID},
        available_tasks={
            DAG_ID: {TASK_ID},
        },
    )

    assert remediation.validation is not None
    assert remediation.validation.valid is False
    assert remediation.status == ActionStatus.PROPOSED


def test_execution_without_validation_is_blocked():
    service, executor, _ = make_service()

    remediation = service.create_action(
        action=make_action(),
        created_by="test-user",
    )

    try:
        service.execute(remediation)
        assert False, "Execution should have been blocked."
    except ValueError as exc:
        assert "not been validated" in str(exc)

    executor.execute.assert_not_called()


def test_execution_without_approval_is_blocked():
    service, executor, _ = make_service()

    remediation = service.create_action(
        action=make_action(),
        created_by="test-user",
    )

    service.validate(
        remediation=remediation,
        user_role="L1",
        available_dags={DAG_ID},
        available_tasks={
            DAG_ID: {TASK_ID},
        },
    )

    try:
        service.execute(remediation)
        assert False, "Execution should have been blocked."
    except PermissionError as exc:
        assert "human approval" in str(exc)

    executor.execute.assert_not_called()


def test_edit_resets_validation_and_approval():
    service, _, _ = make_service()

    remediation = service.create_action(
        action=make_action(),
        created_by="test-user",
    )

    service.validate(
        remediation=remediation,
        user_role="L1",
        available_dags={DAG_ID},
        available_tasks={
            DAG_ID: {TASK_ID},
        },
    )

    assert remediation.status == ActionStatus.PENDING_APPROVAL
    assert remediation.validation is not None

    remediation = service.edit(
        remediation=remediation,
        parameters={"mode": "recovery"},
        reason="Updated remediation plan.",
    )

    assert remediation.status == ActionStatus.PROPOSED
    assert remediation.validation is None
    assert remediation.approval is None
    assert remediation.request.parameters == {
        "mode": "recovery"
    }
    assert remediation.request.reason == "Updated remediation plan."

def test_create_action_preserves_creator_role():
    from backend.app.action_models import (
        ActionRequest,
        ActionType,
        RequiredRole,
    )
    from backend.app.action_service import ActionService
    from backend.app.actions.airflow import AirflowActionExecutor

    service = ActionService(
        airflow_executor=AirflowActionExecutor()
    )

    action = ActionRequest(
        action_type=ActionType.TRIGGER_DAG,
        dag_id="test_dag",
        reason="Test RBAC role persistence",
    )

    remediation = service.create_action(
        action=action,
        created_by="l2-user",
        created_by_role="L2",
    )

    assert remediation.created_by == "l2-user"
    assert remediation.created_by_role == RequiredRole.L2

def test_edit_preserves_creator_role():
    from backend.app.action_models import (
        ActionRequest,
        ActionType,
        RequiredRole,
    )
    from backend.app.action_service import ActionService
    from backend.app.actions.airflow import AirflowActionExecutor

    service = ActionService(
        airflow_executor=AirflowActionExecutor()
    )

    action = ActionRequest(
        action_type=ActionType.TRIGGER_DAG,
        dag_id="test_dag",
        reason="Test edit RBAC persistence",
    )

    remediation = service.create_action(
        action=action,
        created_by="l2-user",
        created_by_role="L2",
    )

    remediation = service.edit(
        remediation=remediation,
        parameters={"mode": "recovery"},
        reason="Edited by authorized engineer",
    )

    assert remediation.created_by_role == RequiredRole.L2
    assert remediation.request.parameters == {
        "mode": "recovery"
    }