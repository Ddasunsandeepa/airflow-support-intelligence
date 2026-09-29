import json
import os

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.developer_llm import request_structured_llm


class IncidentLLMResult(BaseModel):
    model_config = ConfigDict(strict=True)

    incident_class: Literal["Scheduler", "DAG Parsing", "Resource", "Kubernetes", "Configuration", "Unknown"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    reasoning: str
    supporting_evidence: list[str]
    l1_checks: list[str]
    escalation_needed: bool
    escalation_reason: str


INCIDENT_CLASSES = [
    "Scheduler",
    "DAG Parsing",
    "Resource",
    "Kubernetes",
    "Configuration",
    "Unknown",
]


def build_llm_prompt(evidence: dict, ml_result: dict | None = None) -> str:
    """
    Build a structured investigation prompt for the LLM.

    The LLM receives operational evidence and, when available,
    the structured ML result as additional context.
    """

    ml_context = ml_result or {}

    return f"""
You are an Airflow support intelligence assistant.

Your role is to help an L1 support engineer investigate
Airflow incidents.

You MUST reason only from the evidence provided.

Do not invent:
- logs
- metrics
- infrastructure events
- configuration changes
- customer information
- root causes that are not supported by evidence

Supported incident classes:

{json.dumps(INCIDENT_CLASSES, indent=2)}

Airflow evidence:

{json.dumps(evidence, indent=2)}

Existing machine-learning result, if available:

{json.dumps(ml_context, indent=2)}

Analyze the evidence and return a JSON object with exactly
these fields:

{{
  "incident_class": "Scheduler | DAG Parsing | Resource | Kubernetes | Configuration | Unknown",
  "confidence": 0.0,
  "reasoning": "Short evidence-based explanation",
  "supporting_evidence": [
    "Evidence item 1",
    "Evidence item 2"
  ],
  "l1_checks": [
    "Recommended L1 check 1",
    "Recommended L1 check 2"
  ],
  "escalation_needed": false,
  "escalation_reason": "Reason or empty string"
}}

Important rules:

1. Use "Unknown" when evidence is insufficient.
2. Do not treat the DAG name alone as proof of root cause.
3. Do not assume that every RuntimeError has the same cause.
4. Prefer explicit operational evidence over assumptions.
5. Keep confidence conservative.
6. Recommendations must be investigation guidance only.
7. Never recommend automatic production changes.
8. The human support engineer remains responsible for
   operational decisions.
"""


def analyze_with_llm(
    evidence: dict,
    ml_result: dict | None = None,
) -> dict:
    """
    Send Airflow evidence to the configured LLM.

    Returns a structured analysis result.
    """

    result = request_structured_llm(
        build_llm_prompt(evidence=evidence, ml_result=ml_result),
        IncidentLLMResult,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
    )
    if result["status"] == "success":
        return result
    return {
        "status": result["status"],
        "incident_class": "Unknown",
        "confidence": None,
        "reasoning": "LLM analysis unavailable; using structured evidence and ML analysis.",
        "supporting_evidence": [],
        "l1_checks": [],
        "escalation_needed": True,
        "escalation_reason": "LLM analysis unavailable; review the collected evidence.",
    }
