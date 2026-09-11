from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    RETRY_FAILED_TASK = "retry_failed_task"
    CLEAR_TASK = "clear_task"
    TRIGGER_DAG = "trigger_dag"
    PAUSE_DAG = "pause_dag"
    UNPAUSE_DAG = "unpause_dag"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RequiredRole(str, Enum):
    L1 = "L1"
    L2 = "L2"
    ADMIN = "ADMIN"


class ActionRequest(BaseModel):
    """
    A structured remediation action proposed by the intelligence layer
    and reviewed by an authorized engineer.
    """

    action_type: ActionType

    dag_id: str = Field(min_length=1)

    task_id: Optional[str] = None

    parameters: Dict[str, Any] = Field(default_factory=dict)

    reason: str = Field(min_length=1)

    source: str = "human_review"


class ActionPolicy(BaseModel):
    """
    Policy describing how a remediation action is governed.
    """

    action_type: ActionType

    risk_level: RiskLevel

    required_role: RequiredRole

    approval_required: bool = True

    enabled: bool = True


class ActionValidationResult(BaseModel):
    """
    Result produced by the action validation layer.
    """

    valid: bool

    action_type: ActionType

    risk_level: RiskLevel

    required_role: RequiredRole

    approval_required: bool

    errors: list[str] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)


from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ActionApproval(BaseModel):
    """
    Immutable-style approval record for a remediation action.

    In the later authentication layer, approved_by will come from
    the authenticated user identity rather than frontend input.
    """

    approval_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    action_id: str

    decision: ApprovalDecision

    approved_by: str = Field(min_length=1)

    approver_role: RequiredRole

    comment: Optional[str] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RemediationAction(BaseModel):
    """
    Tracks one remediation request through its lifecycle.
    """

    action_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    request: ActionRequest

    status: ActionStatus = ActionStatus.PROPOSED

    created_by: str = Field(min_length=1)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    validation: Optional[ActionValidationResult] = None

    approval: Optional[ActionApproval] = None