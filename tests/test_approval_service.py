import pytest

from backend.app.action_models import (
    ActionRequest,
    ActionStatus,
    ActionValidationResult,
    RemediationAction,
    RequiredRole,
    RiskLevel,
)
from backend.app.action_service import ActionService

from backend.app.approval import (
    approve_action,
    reject_action,
)


DAG_ID = "support_intelligence_recoverable_failure"
TASK_ID = "recoverable_task"


def make_action():
    return ActionRequest(
        action_type="trigger_dag",
        dag_id=DAG_ID,
        parameters={"mode": "recovery"},
        reason="Test approved recovery trigger.",
        source="test",
    )


def make_validated_action():
    executor = None

    service = ActionService(
        airflow_executor=executor,
    )

    remediation = service.create_action(
        action=make_action(),
        created_by="test-user",
    )

    service.validate(
        remediation=remediation,
        user_role="L1",
        available_dags={DAG_ID},
    )

    assert remediation.status == ActionStatus.PENDING_APPROVAL
    assert remediation.validation is not None
    assert remediation.validation.valid is True

    return remediation


def test_l1_can_approve_low_risk_action():
    remediation = make_validated_action()

    result = approve_action(
        remediation=remediation,
        approved_by="l1-user",
        approver_role="L1",
        comment="Approved for recovery test.",
    )

    assert result.status == ActionStatus.APPROVED
    assert result.approval is not None
    assert result.approval.decision.value == "approved"
    assert result.approval.approved_by == "l1-user"
    assert result.approval.approver_role.value == "L1"


def test_unsupported_approver_role_is_rejected():
    remediation = make_validated_action()

    with pytest.raises(
        ValueError,
        match="Unsupported approver role",
    ):
        approve_action(
            remediation=remediation,
            approved_by="unknown-user",
            approver_role="L99",
        )


def test_approval_requires_validation():
    executor = None

    service = ActionService(
        airflow_executor=executor,
    )

    remediation = service.create_action(
        action=make_action(),
        created_by="test-user",
    )

    with pytest.raises(
        ValueError,
        match="before validation",
    ):
        approve_action(
            remediation=remediation,
            approved_by="l1-user",
            approver_role="L1",
        )


def test_approval_cannot_be_repeated_after_approval():
    remediation = make_validated_action()

    approve_action(
        remediation=remediation,
        approved_by="l1-user",
        approver_role="L1",
    )

    with pytest.raises(
        ValueError,
        match="cannot be approved from status",
    ):
        approve_action(
            remediation=remediation,
            approved_by="another-user",
            approver_role="L1",
        )


def test_rejection_moves_action_to_rejected():
    remediation = make_validated_action()

    result = reject_action(
        remediation=remediation,
        rejected_by="l1-user",
        rejector_role="L1",
        comment="Rejected for testing.",
    )

    assert result.status == ActionStatus.REJECTED
    assert result.approval is not None
    assert result.approval.decision.value == "rejected"
    assert result.approval.approved_by == "l1-user"
    assert result.approval.approver_role.value == "L1"


def test_rejected_action_cannot_be_approved():
    remediation = make_validated_action()

    reject_action(
        remediation=remediation,
        rejected_by="l1-user",
        rejector_role="L1",
    )

    with pytest.raises(
        ValueError,
        match="cannot be approved from status",
    ):
        approve_action(
            remediation=remediation,
            approved_by="l1-user",
            approver_role="L1",
        )

def test_l1_cannot_reject_medium_risk_action():
    from backend.app.action_models import (
        ActionRequest,
        ActionType,
        ActionStatus,
    )
    from backend.app.approval import reject_action
    import pytest

    remediation = RemediationAction(
        request=ActionRequest(
            action_type=ActionType.PAUSE_DAG,
            dag_id="test_dag",
            reason="Test medium-risk rejection",
        ),
        created_by="l2-user",
        created_by_role="L2",
        status=ActionStatus.PENDING_APPROVAL,
    )

    remediation.validation = ActionValidationResult(
        valid=True,
        action_type=ActionType.PAUSE_DAG,
        risk_level=RiskLevel.MEDIUM,
        required_role=RequiredRole.L2,
        approval_required=True,
    )

    with pytest.raises(PermissionError):
        reject_action(
            remediation=remediation,
            rejected_by="l1-user",
            rejector_role="L1",
        )
def test_invalid_action_cannot_be_rejected():
    from backend.app.action_models import (
        ActionRequest,
        ActionType,
        ActionStatus,
    )
    from backend.app.approval import reject_action
    import pytest

    remediation = RemediationAction(
        request=ActionRequest(
            action_type=ActionType.TRIGGER_DAG,
            dag_id="test_dag",
            reason="Test invalid rejection",
        ),
        created_by="l1-user",
        created_by_role="L1",
        status=ActionStatus.PENDING_APPROVAL,
    )

    remediation.validation = ActionValidationResult(
        valid=False,
        action_type=ActionType.TRIGGER_DAG,
        risk_level=RiskLevel.LOW,
        required_role=RequiredRole.L1,
        approval_required=True,
        errors=["DAG validation failed"],
    )

    with pytest.raises(ValueError):
        reject_action(
            remediation=remediation,
            rejected_by="l1-user",
            rejector_role="L1",
        )