from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from datetime import datetime, timezone
from uuid import uuid4


class ChangeType(str, Enum):
    RUNTIME_CONFIGURATION = "runtime_configuration"
    SOURCE_CODE = "source_code"


class ChangeEntry(BaseModel):
    """
    Represents one individual value changed by a remediation proposal.
    """

    path: str
    before: Any = None
    after: Any = None

class SourceCodeChange(BaseModel):
    file_path: str = Field(min_length=1)
    language: str = "python"
    before_code: str
    proposed_code: str
    generated_by: Literal["controlled_fallback", "controlled_demo_fallback", "developer_llm", "no_proposal"] | None = None

class ChangeProposal(BaseModel):
    """
    Human-reviewable representation of the exact change proposed
    by a remediation action.

    This model describes the change only.
    It does not execute or authorize the change.
    """

    change_type: ChangeType

    target: str = Field(min_length=1)

    title: str = Field(min_length=1)

    description: str = Field(min_length=1)

    before: dict[str, Any] = Field(default_factory=dict)

    after: dict[str, Any] = Field(default_factory=dict)

    changes: list[ChangeEntry] = Field(default_factory=list)

    source_code: SourceCodeChange | None = None

    unified_diff: str = ""

    additions: int = 0

    deletions: int = 0


class SourceRemediationState(str, Enum):
    PROPOSED = "proposed"
    EDITED = "edited"
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLYING = "applying"
    APPLIED = "applied"
    AIRFLOW_VALIDATING = "airflow_validating"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    STALE_SOURCE = "stale_source"
    APPLY_FAILED = "apply_failed"
    APPLY_FAILED_ROLLED_BACK = "apply_failed_rolled_back"
    AIRFLOW_PARSE_FAILED = "airflow_parse_failed"
    EXECUTION_FAILED = "execution_failed"
    VERIFICATION_FAILED = "verification_failed"


class SourceRevision(BaseModel):
    revision: int
    source: str
    source_hash: str
    edited_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceValidation(BaseModel):
    valid: bool
    revision: int
    source_hash: str
    checks: dict[str, bool] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceApproval(BaseModel):
    revision: int
    source_hash: str
    approved_by: str
    approver_role: Literal["L2", "ADMIN"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceAuditEvent(BaseModel):
    state: SourceRemediationState
    message: str
    revision: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceRemediation(BaseModel):
    execution_allowed: bool = False
    execution_policy_version: int = 1
    execution_block_reason: str | None = None
    investigation: dict[str, Any] = Field(default_factory=dict)
    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    dag_id: str
    target_function: str
    change: ChangeProposal
    base_source_hash: str
    original_proposed_source: str
    proposal_hash: str
    revision: int = 1
    revisions: list[SourceRevision] = Field(default_factory=list)
    state: SourceRemediationState = SourceRemediationState.PROPOSED
    validation: SourceValidation | None = None
    approval: SourceApproval | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    tests_to_run: list[str] = Field(default_factory=list)
    audit: list[SourceAuditEvent] = Field(default_factory=list)
    backup_path: str | None = None
    applied_at: datetime | None = None
    airflow_parse: dict[str, Any] | None = None
    dag_run_id: str | None = None
    verification: dict[str, Any] | None = None
    feedback_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def reflect_execution_policy(self):
        from backend.app.source_execution_policy import check_record_policy
        try:
            check_record_policy(self)
            self.execution_allowed = True
            self.execution_block_reason = None
        except (ValueError, SyntaxError, TypeError, AttributeError) as exc:
            self.execution_allowed = False
            self.execution_block_reason = str(exc)
        return self
