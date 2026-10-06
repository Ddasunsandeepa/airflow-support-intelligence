"""Source endpoints deliberately separate from the existing runtime action API."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from backend.app.source_remediation import SourceRemediationService, TERMINAL
from backend.app.source_remediation_store import workflow_lock
from backend.app.feedback_models import RemediationFeedback, RemediationFeedbackRequest

router = APIRouter(prefix="/source-remediations", tags=["Source remediation"])


class ReviewVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class EditSourceRequest(ReviewVersion):
    proposed_source: str = Field(min_length=1, max_length=50000)
    edited_by: str = Field(min_length=1, max_length=100)


class SourceApprovalRequest(ReviewVersion):
    approved_by: str = Field(min_length=1, max_length=100)
    approver_role: Literal["L2", "ADMIN"]


def invoke(operation):
    try:
        return operation()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("")
def list_source_remediations():
    return invoke(lambda: SourceRemediationService().store.all())


@router.get("/{proposal_id}")
def get_source_remediation(proposal_id: str):
    return invoke(lambda: SourceRemediationService().store.get(proposal_id))


@router.put("/{proposal_id}/source")
def edit_source(proposal_id: str, request: EditSourceRequest):
    return invoke(lambda: SourceRemediationService().edit(proposal_id, request.revision, request.source_hash,
                                                         request.proposed_source, request.edited_by))


@router.post("/{proposal_id}/reset")
def reset_source(proposal_id: str, request: ReviewVersion):
    def reset():
        service = SourceRemediationService()
        with workflow_lock:
            original = service.store.get(proposal_id).original_proposed_source
            return service.edit(proposal_id, request.revision, request.source_hash, original, "engineer-reset")
    return invoke(reset)


@router.post("/{proposal_id}/validate")
def validate_source(proposal_id: str, request: ReviewVersion):
    return invoke(lambda: SourceRemediationService().validate(proposal_id, request.revision, request.source_hash))


@router.post("/{proposal_id}/approve")
def approve_source(proposal_id: str, request: SourceApprovalRequest):
    return invoke(lambda: SourceRemediationService().approve(proposal_id, request.revision, request.source_hash,
                                                            request.approved_by, request.approver_role))


@router.post("/{proposal_id}/reject")
def reject_source(proposal_id: str, request: ReviewVersion):
    return invoke(lambda: SourceRemediationService().reject(proposal_id, request.revision, request.source_hash))


@router.post("/{proposal_id}/execute")
def execute_source(proposal_id: str, request: ReviewVersion):
    return invoke(lambda: SourceRemediationService().execute(proposal_id, request.revision, request.source_hash))


@router.get("/{proposal_id}/feedback", response_model=RemediationFeedback | None)
def get_feedback(proposal_id: str):
    from backend.app.main import feedback_store
    def get():
        SourceRemediationService().store.get(proposal_id)
        return feedback_store.get_for_action(proposal_id)
    return invoke(get)


@router.post("/{proposal_id}/feedback", response_model=RemediationFeedback)
def submit_feedback(proposal_id: str, request: RemediationFeedbackRequest):
    from backend.app.main import feedback_store
    def submit():
        with workflow_lock:
            service = SourceRemediationService()
            record = service.store.get(proposal_id)
            if record.state not in TERMINAL:
                raise ValueError("Feedback is available after remediation reaches a terminal result.")
            feedback = feedback_store.save(RemediationFeedback(action_id=proposal_id, **request.model_dump()))
            record.feedback_id = feedback.feedback_id
            service.store.save(record)
            return feedback
    return invoke(submit)
