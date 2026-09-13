from typing import List, Optional

from pydantic import BaseModel, Field


class DeveloperChatRequest(BaseModel):
    """
    Request submitted to the Airflow Developer Copilot.
    """

    message: str = Field(min_length=1)
    dag_id: Optional[str] = None


class DiagnosisResult(BaseModel):
    """
    Structured incident diagnosis returned by the Copilot.
    """

    incident_class: str
    summary: str
    confidence: Optional[float] = None


class CodeChangeProposal(BaseModel):
    """
    Proposed code change.

    The Copilot may suggest a change, but this proposal is
    never written directly into an Airflow deployment.
    """

    available: bool = False
    summary: Optional[str] = None
    proposed_code: Optional[str] = None
    reason: Optional[str] = None


class DeveloperChatResponse(BaseModel):
    """
    Structured response returned by the Developer Copilot.
    """

    status: str
    message: str
    dag_id: Optional[str] = None

    diagnosis: Optional[DiagnosisResult] = None

    evidence: List[str] = Field(default_factory=list)

    reasoning: Optional[str] = None

    recommended_fix: Optional[str] = None

    code_change: CodeChangeProposal = Field(
        default_factory=CodeChangeProposal
    )

    tests_to_run: List[str] = Field(default_factory=list)

    human_review_required: bool = True