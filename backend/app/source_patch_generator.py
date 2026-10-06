from pydantic import BaseModel, ConfigDict, Field

from backend.app.developer_llm import request_structured_llm


class StructuredSourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    target_function: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    proposed_function: str = Field(min_length=1, max_length=20000)
    tests_to_run: list[str]


def propose_evidence_grounded_patch(dag_id: str, source: str, context: dict, *, allow_demo_fallback: bool = False):
    """Compatibility entry point; fallback always requires explicit opt-in."""
    from backend.app.ai_source_investigation import investigate_source
    result = investigate_source(dag_id, source, context, allow_demo_fallback=allow_demo_fallback)
    return result.get("proposal")
