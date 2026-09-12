from unittest.mock import Mock

import pytest

from backend.app.action_models import (
    ActionApproval,
    ActionRequest,
    ActionStatus,
    ApprovalDecision,
    RequiredRole,
)
from backend.app.action_service import ActionService


DAG_ID = "support_intelligence_recoverable_failure"


def make_trigger_action():
    return ActionRequest(
        action_type="trigger_dag",
        dag_id=DAG_ID,
        parameters={
            "mode": "recovery",
        },
        reason="Test approved recovery trigger.",
        source="test",
    )


def prepare_approved_action(service):
    remediation = service.create_action(
        action=make_trigger_action(),
        created_by="test-user",
    )

    service.validate(
        remediation=remediation,
        user_role="L1",
        available_dags={DAG_ID},
    )

    assert remediation.status == ActionStatus.PENDING_APPROVAL

    remediation.approval = ActionApproval(
        action_id=remediation.action_id,
        decision=ApprovalDecision.APPROVED,
        approved_by="test-approver",
        approver_role=RequiredRole.L1,
        comment="Approved for test execution.",
    )

    remediation.status = ActionStatus.APPROVED

    return remediation


def test_approved_trigger_is_executed_and_verified():
    executor = Mock()
    verification_engine = Mock()

    executor.supports.return_value = True

    executor.execute.return_value = {
        "status": "submitted",
        "action": "trigger_dag",
        "dag_id": DAG_ID,
        "dag_run_id": "test-run-123",
        "airflow_state": "queued",
    }

    verification_engine.verify_dag_run.return_value = {
        "status": "verified",
        "dag_id": DAG_ID,
        "dag_run_id": "test-run-123",
    }

    service = ActionService(
        airflow_executor=executor,
        verification_engine=verification_engine,
    )

    remediation = prepare_approved_action(service)

    result = service.execute(remediation)

    assert result["status"] == "succeeded"
    assert remediation.status == ActionStatus.SUCCEEDED

    executor.execute.assert_called_once_with(
        remediation.request
    )

    verification_engine.verify_dag_run.assert_called_once_with(
        dag_id=DAG_ID,
        dag_run_id="test-run-123",
    )


def test_approved_trigger_fails_when_verification_fails():
    executor = Mock()
    verification_engine = Mock()

    executor.supports.return_value = True

    executor.execute.return_value = {
        "status": "submitted",
        "action": "trigger_dag",
        "dag_id": DAG_ID,
        "dag_run_id": "test-run-456",
        "airflow_state": "queued",
    }

    verification_engine.verify_dag_run.return_value = {
        "status": "verification_failed",
        "dag_id": DAG_ID,
        "dag_run_id": "test-run-456",
        "reason": "DAG run failed.",
    }

    service = ActionService(
        airflow_executor=executor,
        verification_engine=verification_engine,
    )

    remediation = prepare_approved_action(service)

    result = service.execute(remediation)

    assert result["status"] == "failed"
    assert remediation.status == ActionStatus.FAILED
    assert result["verification"]["status"] == (
        "verification_failed"
    )


def test_trigger_fails_when_airflow_returns_no_dag_run_id():
    executor = Mock()
    verification_engine = Mock()

    executor.supports.return_value = True

    executor.execute.return_value = {
        "status": "submitted",
        "action": "trigger_dag",
        "dag_id": DAG_ID,
        "dag_run_id": None,
        "airflow_state": "queued",
    }

    service = ActionService(
        airflow_executor=executor,
        verification_engine=verification_engine,
    )

    remediation = prepare_approved_action(service)

    result = service.execute(remediation)

    assert result["status"] == "failed"
    assert remediation.status == ActionStatus.FAILED
    assert result["verification"]["status"] == (
        "verification_failed"
    )

    verification_engine.verify_dag_run.assert_not_called()


def test_executor_exception_marks_action_failed():
    executor = Mock()
    verification_engine = Mock()

    executor.supports.return_value = True

    executor.execute.side_effect = RuntimeError(
        "Synthetic executor failure"
    )

    service = ActionService(
        airflow_executor=executor,
        verification_engine=verification_engine,
    )

    remediation = prepare_approved_action(service)

    with pytest.raises(RuntimeError, match="Synthetic executor failure"):
        service.execute(remediation)

    assert remediation.status == ActionStatus.FAILED
    verification_engine.verify_dag_run.assert_not_called()