from typing import Any, Dict, Optional

from backend.app.action_models import (
    ActionRequest,
    ActionValidationResult,
    ActionType,
    RequiredRole,
)

from backend.app.action_registry import get_action_policy


# Role hierarchy.
# Higher roles inherit the permissions of lower roles.
ROLE_LEVELS = {
    RequiredRole.L1: 1,
    RequiredRole.L2: 2,
    RequiredRole.ADMIN: 3,
}


def _normalise_role(role: str) -> Optional[RequiredRole]:
    """
    Convert a user-provided role into the supported RequiredRole enum.

    Returns None when the role is not recognised.
    """

    if not role:
        return None

    normalised = role.strip().upper()

    for supported_role in RequiredRole:
        if normalised == supported_role.value:
            return supported_role

    return None


def _has_required_role(
    user_role: RequiredRole,
    required_role: RequiredRole,
) -> bool:
    """
    Check whether the user's role is sufficient for the action.
    """

    user_level = ROLE_LEVELS[user_role]
    required_level = ROLE_LEVELS[required_role]

    return user_level >= required_level


def validate_action(
    action: ActionRequest,
    user_role: str,
    available_dags: Optional[set[str]] = None,
    available_tasks: Optional[Dict[str, set[str]]] = None,
) -> ActionValidationResult:
    """
    Validate a remediation action before it can proceed.

    Validation covers:

    - Registered action
    - Action enabled by policy
    - User role
    - DAG target
    - Task target
    - Basic action requirements

    This function does NOT execute anything.
    """

    errors: list[str] = []
    warnings: list[str] = []

    # ---------------------------------------------------------
    # 1. Resolve user role
    # ---------------------------------------------------------

    resolved_role = _normalise_role(user_role)

    if resolved_role is None:
        errors.append(
            f"Unsupported user role: {user_role}"
        )

        # We cannot safely determine authorization without a valid role.
        return ActionValidationResult(
            valid=False,
            action_type=action.action_type,
            risk_level=get_action_policy(
                action.action_type
            ).risk_level,
            required_role=get_action_policy(
                action.action_type
            ).required_role,
            approval_required=get_action_policy(
                action.action_type
            ).approval_required,
            errors=errors,
            warnings=warnings,
        )

    # ---------------------------------------------------------
    # 2. Get action policy
    # ---------------------------------------------------------

    try:
        policy = get_action_policy(action.action_type)

    except ValueError as exc:
        errors.append(str(exc))

        # This should normally be unreachable because ActionType
        # is already an allowlisted enum, but we keep the validator
        # defensive.
        raise

    # ---------------------------------------------------------
    # 3. Check whether action is enabled
    # ---------------------------------------------------------

    if not policy.enabled:
        errors.append(
            f"Action '{action.action_type.value}' is currently disabled."
        )

    # ---------------------------------------------------------
    # 4. Check user authorization
    # ---------------------------------------------------------

    if not _has_required_role(
        resolved_role,
        policy.required_role,
    ):
        errors.append(
            f"Role '{resolved_role.value}' is not authorized for "
            f"action '{action.action_type.value}'. "
            f"Required role: '{policy.required_role.value}'."
        )

    # ---------------------------------------------------------
    # 5. Validate DAG target
    # ---------------------------------------------------------

    if not action.dag_id.strip():
        errors.append("dag_id cannot be empty.")

    elif available_dags is not None:
        if action.dag_id not in available_dags:
            errors.append(
                f"DAG '{action.dag_id}' was not found in the "
                "available Airflow DAG catalog."
            )

    # ---------------------------------------------------------
    # 6. Validate task requirements
    # ---------------------------------------------------------

    task_required_actions = {
        ActionType.RETRY_FAILED_TASK,
        ActionType.CLEAR_TASK,
    }

    if action.action_type in task_required_actions:
        if not action.task_id:
            errors.append(
                f"Action '{action.action_type.value}' requires a task_id."
            )

        elif available_tasks is not None:
            dag_tasks = available_tasks.get(
                action.dag_id,
                set(),
            )

            if action.task_id not in dag_tasks:
                errors.append(
                    f"Task '{action.task_id}' was not found in DAG "
                    f"'{action.dag_id}'."
                )

    # ---------------------------------------------------------
    # 7. Validate action-specific parameters
    # ---------------------------------------------------------

    # For V2.1, the initial allowlisted actions do not require
    # arbitrary parameters.
    #
    # Keeping this validation layer separate means future actions
    # can introduce controlled parameters without changing the
    # execution architecture.

    if not isinstance(action.parameters, dict):
        errors.append(
            "Action parameters must be a dictionary."
        )

    # ---------------------------------------------------------
    # 8. Add safety warning for human review
    # ---------------------------------------------------------

    if policy.approval_required:
        warnings.append(
            "Human approval is required before this action can execute."
        )

    # ---------------------------------------------------------
    # 9. Build final validation result
    # ---------------------------------------------------------

    return ActionValidationResult(
        valid=len(errors) == 0,
        action_type=action.action_type,
        risk_level=policy.risk_level,
        required_role=policy.required_role,
        approval_required=policy.approval_required,
        errors=errors,
        warnings=warnings,
    )