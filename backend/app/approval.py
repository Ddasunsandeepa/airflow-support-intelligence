from backend.app.action_models import (
    ActionApproval,
    ActionStatus,
    ApprovalDecision,
    RemediationAction,
    RequiredRole,
)


ROLE_LEVELS = {
    RequiredRole.L1: 1,
    RequiredRole.L2: 2,
    RequiredRole.ADMIN: 3,
}


def _normalise_role(role: str) -> RequiredRole:
    """
    Convert a role string into a supported RequiredRole.
    """

    normalised = role.strip().upper()

    for supported_role in RequiredRole:
        if normalised == supported_role.value:
            return supported_role

    raise ValueError(
        f"Unsupported approver role: {role}"
    )


def approve_action(
    remediation: RemediationAction,
    approved_by: str,
    approver_role: str,
    comment: str | None = None,
) -> RemediationAction:
    """
    Approve a validated remediation action.

    Approval is permitted only when:
    - validation exists
    - validation succeeded
    - the action has not already been approved/rejected
    - the approver has the required role
    """

    if remediation.validation is None:
        raise ValueError(
            "Action cannot be approved before validation."
        )

    if not remediation.validation.valid:
        raise ValueError(
            "Action cannot be approved because validation failed."
        )

    if remediation.status not in {
        ActionStatus.VALIDATED,
        ActionStatus.PENDING_APPROVAL,
    }:
        raise ValueError(
            f"Action cannot be approved from status "
            f"'{remediation.status.value}'."
        )

    resolved_role = _normalise_role(approver_role)

    required_role = remediation.validation.required_role

    if (
        ROLE_LEVELS[resolved_role]
        < ROLE_LEVELS[required_role]
    ):
        raise PermissionError(
            f"Role '{resolved_role.value}' cannot approve this action. "
            f"Required role: '{required_role.value}'."
        )

    approval = ActionApproval(
        action_id=remediation.action_id,
        decision=ApprovalDecision.APPROVED,
        approved_by=approved_by,
        approver_role=resolved_role,
        comment=comment,
    )

    remediation.approval = approval
    remediation.status = ActionStatus.APPROVED

    return remediation


def reject_action(
    remediation: RemediationAction,
    rejected_by: str,
    rejector_role: str,
    comment: str | None = None,
) -> RemediationAction:
    """
    Reject a validated remediation action.

    Rejection is permitted only when:
    - validation exists
    - validation succeeded
    - the action is awaiting a decision
    - the rejector has the required role
    """

    if remediation.validation is None:
        raise ValueError(
            "Action cannot be rejected before validation."
        )

    if not remediation.validation.valid:
        raise ValueError(
            "Action cannot be rejected because validation failed."
        )

    if remediation.status not in {
        ActionStatus.VALIDATED,
        ActionStatus.PENDING_APPROVAL,
    }:
        raise ValueError(
            f"Action cannot be rejected from status "
            f"'{remediation.status.value}'."
        )

    resolved_role = _normalise_role(rejector_role)

    required_role = remediation.validation.required_role

    if (
        ROLE_LEVELS[resolved_role]
        < ROLE_LEVELS[required_role]
    ):
        raise PermissionError(
            f"Role '{resolved_role.value}' cannot reject this action. "
            f"Required role: '{required_role.value}'."
        )

    approval = ActionApproval(
        action_id=remediation.action_id,
        decision=ApprovalDecision.REJECTED,
        approved_by=rejected_by,
        approver_role=resolved_role,
        comment=comment,
    )

    remediation.approval = approval
    remediation.status = ActionStatus.REJECTED

    return remediation