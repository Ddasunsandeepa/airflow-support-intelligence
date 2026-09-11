from backend.app.action_models import (
    ActionPolicy,
    ActionType,
    RequiredRole,
    RiskLevel,
)


ACTION_POLICIES = {
    ActionType.RETRY_FAILED_TASK: ActionPolicy(
        action_type=ActionType.RETRY_FAILED_TASK,
        risk_level=RiskLevel.LOW,
        required_role=RequiredRole.L1,
        approval_required=True,
    ),

    ActionType.CLEAR_TASK: ActionPolicy(
        action_type=ActionType.CLEAR_TASK,
        risk_level=RiskLevel.LOW,
        required_role=RequiredRole.L1,
        approval_required=True,
    ),

    ActionType.TRIGGER_DAG: ActionPolicy(
        action_type=ActionType.TRIGGER_DAG,
        risk_level=RiskLevel.LOW,
        required_role=RequiredRole.L1,
        approval_required=True,
    ),

    ActionType.PAUSE_DAG: ActionPolicy(
        action_type=ActionType.PAUSE_DAG,
        risk_level=RiskLevel.MEDIUM,
        required_role=RequiredRole.L2,
        approval_required=True,
    ),

    ActionType.UNPAUSE_DAG: ActionPolicy(
        action_type=ActionType.UNPAUSE_DAG,
        risk_level=RiskLevel.MEDIUM,
        required_role=RequiredRole.L2,
        approval_required=True,
    ),
}


def get_action_policy(action_type: ActionType) -> ActionPolicy:
    """
    Return the policy associated with an action.
    """

    policy = ACTION_POLICIES.get(action_type)

    if policy is None:
        raise ValueError(
            f"No policy registered for action: {action_type}"
        )

    return policy