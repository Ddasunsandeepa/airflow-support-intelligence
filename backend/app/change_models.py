from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
