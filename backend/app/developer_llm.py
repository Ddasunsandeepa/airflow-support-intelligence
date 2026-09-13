import json
import os

from openai import OpenAI


def build_developer_prompt(
    message: str,
    incident_type: str,
    incident_reference: str,
    evidence: list[str],
    incident_class: str,
    confidence: float | None,
    recommended_fix: str,
) -> str:
    """
    Build a conservative prompt for the Airflow Developer Copilot.

    The model must reason only from evidence collected by the
    support intelligence platform.
    """

    evidence_text = "\n".join(
        f"- {item}"
        for item in evidence
    )

    confidence_text = (
        str(confidence)
        if confidence is not None
        else "unknown"
    )

    incident_label = (
        "Registered Airflow DAG"
        if incident_type == "dag"
        else "Airflow DAG parsing/import error"
    )

    return f"""
You are an Airflow Developer Copilot.

Your responsibility is to help a software engineer understand
an Airflow incident and decide what should be investigated or
changed.

Developer request:
{message}

Incident type:
{incident_label}

Incident reference:
{incident_reference}

Incident classification:
{incident_class}

Classification confidence:
{confidence_text}

Observed evidence:
{evidence_text}

Existing recommended investigation:
{recommended_fix}

IMPORTANT RULES:

1. Use only the evidence provided above.
2. Do not invent logs, metrics, Kubernetes events, code,
   configuration, infrastructure state, or root causes.
3. Clearly distinguish observed evidence from inference.
4. If the evidence is insufficient, explicitly say so.
5. Do not claim that correlation proves causation.
6. Do not recommend changing source code when the evidence
   indicates an infrastructure-only problem.
7. For DAG parsing/import errors, source-code or dependency
   investigation may be appropriate when the evidence supports it.
8. Do not directly modify Airflow files.
9. Do not execute shell commands, kubectl commands, Python
   code, deployments, or production changes.
10. If a code change may be appropriate, explain why before
    proposing it.
11. Keep the answer useful to a software engineer.

Return ONLY valid JSON using this structure:

{{
  "summary": "Concise answer to the developer's question.",
  "reasoning": "Evidence-based explanation.",
  "recommended_fix": "Recommended next step or fix.",
  "code_change_available": false,
  "code_change_summary": "Why a source-code change is or is not appropriate.",
  "tests_to_run": [
    "Validation step 1",
    "Validation step 2"
  ]
}}
""".strip()


def analyze_with_developer_llm(
    message: str,
    incident_type: str,
    incident_reference: str,
    evidence: list[str],
    incident_class: str,
    confidence: float | None,
    recommended_fix: str,
) -> dict:
    """
    Ask the configured LLM to answer the developer's request.

    This function is advisory only. It never executes actions
    or modifies Airflow source files.
    """

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return {
            "status": "not_configured",
            "summary": (
                "Developer Copilot LLM is not configured. "
                "The evidence-based analysis remains available."
            ),
            "reasoning": "",
            "recommended_fix": recommended_fix,
            "code_change_available": False,
            "code_change_summary": (
                "LLM configuration is required before "
                "developer-specific reasoning is available."
            ),
            "tests_to_run": [],
        }

    client = OpenAI(api_key=api_key)

    prompt = build_developer_prompt(
        message=message,
        incident_type=incident_type,
        incident_reference=incident_reference,
        evidence=evidence,
        incident_class=incident_class,
        confidence=confidence,
        recommended_fix=recommended_fix,
    )

    response = client.responses.create(
        model=os.getenv(
            "DEVELOPER_COPILOT_MODEL",
            "gpt-5.6-luna",
        ),
        input=prompt,
    )

    output_text = response.output_text.strip()

    try:
        result = json.loads(output_text)
    except json.JSONDecodeError:
        return {
            "status": "invalid_llm_response",
            "summary": output_text,
            "reasoning": "",
            "recommended_fix": recommended_fix,
            "code_change_available": False,
            "code_change_summary": (
                "The model response could not be parsed "
                "as structured Copilot output."
            ),
            "tests_to_run": [],
        }

    return {
        "status": "success",
        "summary": result.get("summary", ""),
        "reasoning": result.get("reasoning", ""),
        "recommended_fix": result.get(
            "recommended_fix",
            recommended_fix,
        ),
        "code_change_available": bool(
            result.get("code_change_available", False)
        ),
        "code_change_summary": result.get(
            "code_change_summary",
            "",
        ),
        "tests_to_run": result.get(
            "tests_to_run",
            [],
        ),
    }