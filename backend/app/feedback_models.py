from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class FeedbackQuality(str, Enum):
    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"


class RemediationFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    useful: bool = Field(strict=True)

    change_quality: FeedbackQuality

    comment: Optional[str] = Field(default=None, max_length=4000)


class RemediationFeedback(BaseModel):
    feedback_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    action_id: str

    useful: bool

    change_quality: FeedbackQuality

    comment: Optional[str] = None

    submitted_by: str = "l1-user"

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
