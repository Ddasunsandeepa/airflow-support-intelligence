import json
import os

from openai import OpenAI


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

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return {
            "status": "not_configured",
            "incident_class": "Unknown",
            "confidence": None,
            "reasoning": (
                "LLM analysis is not configured because "
                "OPENAI_API_KEY is not available."
            ),
            "supporting_evidence": [],
            "l1_checks": [],
            "escalation_needed": False,
            "escalation_reason": "",
        }

    client = OpenAI(api_key=api_key)

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna",
    )

    prompt = build_llm_prompt(
        evidence=evidence,
        ml_result=ml_result,
    )

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    raw_output = response.output_text

    try:
        result = json.loads(raw_output)
    except json.JSONDecodeError:
        return {
            "status": "invalid_response",
            "incident_class": "Unknown",
            "confidence": None,
            "reasoning": (
                "The LLM returned a response that could not "
                "be parsed as structured JSON."
            ),
            "supporting_evidence": [],
            "l1_checks": [],
            "escalation_needed": True,
            "escalation_reason": (
                "LLM response format could not be validated."
            ),
        }

    result["status"] = "success"

    return result