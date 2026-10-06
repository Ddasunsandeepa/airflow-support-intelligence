import logging
import os
import re
from typing import TypeVar
from urllib.parse import quote

import requests
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict


logger = logging.getLogger(__name__)
ResultModel = TypeVar("ResultModel", bound=BaseModel)


class DeveloperLLMResult(BaseModel):
    model_config = ConfigDict(strict=True)

    summary: str
    reasoning: str
    recommended_fix: str
    code_change_available: bool
    code_change_summary: str
    tests_to_run: list[str]


def _request_provider(provider: str, prompt: str, schema: dict, openai_model: str) -> str:
    """One bounded request; never execute model output or retry exhausted credits."""
    if provider == "openai":
        with OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=30, max_retries=0) as client:
            return client.responses.create(model=openai_model, input=prompt).output_text

    if provider == "gemini":
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(model, safe='')}:generateContent",
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                },
            },
            timeout=(5, 30),
        )
        response.raise_for_status()
        candidate = response.json()["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError("Incomplete Gemini response")
        return "".join(
            part.get("text", "") for part in candidate["content"]["parts"]
            if not part.get("thought")
        )

    response = requests.post(
        os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/chat",
        json={
            "model": os.environ["OLLAMA_MODEL"],
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,
        },
        timeout=(5, 60),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("done") or payload.get("done_reason") == "length":
        raise ValueError("Incomplete Ollama response")
    return payload["message"]["content"]


def request_structured_llm(
    prompt: str, result_model: type[ResultModel], *, openai_model: str, diagnostics: bool = False
) -> dict:
    """Shared transport for the two existing analysis prompts and response contracts.

    OpenAI remains the legacy default. Additional providers are tried only when
    explicitly listed in LLM_FALLBACK_PROVIDERS. Failure lets callers retain
    their existing deterministic evidence/ML analysis.
    """
    primary = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    attempts = []
    def failure(status):
        return {"status": status, **({"provider_attempts": attempts} if diagnostics else {})}
    if primary == "none":
        return failure("not_configured")
    providers = list(dict.fromkeys([
        primary,
        *[item.strip().lower() for item in os.getenv("LLM_FALLBACK_PROVIDERS", "").split(",") if item.strip()],
    ]))
    status = "not_configured"
    for provider in providers:
        model = {"gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), "openai": openai_model,
                 "ollama": os.getenv("OLLAMA_MODEL", "")}.get(provider, "")
        attempt = {"provider": provider, "model": model, "status": "not_configured"}
        attempts.append(attempt)
        required = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "ollama": "OLLAMA_MODEL"}
        if provider not in required:
            logger.warning("Unsupported LLM provider configuration; using evidence fallback.")
            continue
        if not os.getenv(required[provider], "").strip():
            logger.warning("LLM provider %s is missing %s.", provider, required[provider])
            continue
        try:
            output = _request_provider(provider, prompt, result_model.model_json_schema(), openai_model)
            result = result_model.model_validate_json(output).model_dump()
            attempt["status"] = "success"
            if diagnostics:
                return {"status": "success", "result": result, "provider_attempts": attempts}
            return {**result, "status": "success"}
        except (OpenAIError, requests.RequestException) as exc:
            status = "provider_unavailable"
            attempt.update(safe_provider_error(exc))
            attempt["status"] = status
            # Do not log provider response bodies, credentials, or incident evidence.
            logger.warning("LLM provider %s unavailable (%s); trying fallback.", provider, type(exc).__name__)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            status = "invalid_llm_response"
            attempt.update(status=status, error_category=type(exc).__name__, message="Provider output did not match the requested schema or was incomplete.")
            logger.warning("LLM provider %s returned invalid output (%s); trying fallback.", provider, type(exc).__name__)
    return failure(status)


def safe_provider_error(exc) -> dict:
    """Diagnostic metadata only: never exception URLs, headers, keys or raw payloads."""
    response = getattr(exc, "response", None)
    http_status = getattr(response, "status_code", None)
    result = {"http_status": http_status if isinstance(http_status, int) else None,
              "error_category": type(exc).__name__}
    try:
        body = response.json() if response is not None else {}
        error = body.get("error", {}) if isinstance(body, dict) else {}
        if isinstance(error, dict):
            category = error.get("status") or error.get("code")
            if isinstance(category, (str, int)):
                result["error_category"] = str(category)[:80]
            message = error.get("message", "")
            if isinstance(message, str):
                for name in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
                    secret = os.getenv(name)
                    if secret:
                        message = message.replace(secret, "[REDACTED]")
                message = re.sub(r"(?:AIza[\w-]+|sk-[\w-]+)", "[REDACTED]", message)
                message = re.sub(r"(?i)(key|token|authorization)=\S+", r"\1=[REDACTED]", message)
                result["message"] = message[:800]
    except (ValueError, TypeError, AttributeError):
        pass
    return result


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

    
    prompt = build_developer_prompt(
        message=message,
        incident_type=incident_type,
        incident_reference=incident_reference,
        evidence=evidence,
        incident_class=incident_class,
        confidence=confidence,
        recommended_fix=recommended_fix,
    )

    result = request_structured_llm(
        prompt,
        DeveloperLLMResult,
        openai_model=os.getenv("DEVELOPER_COPILOT_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
    )
    if result["status"] == "success":
        return result
    return {
        "status": result["status"],
        "summary": "Developer LLM unavailable; using evidence-based analysis.",
        "reasoning": "",
        "recommended_fix": recommended_fix,
        "code_change_available": False,
        "code_change_summary": "No LLM-generated source change is available.",
        "tests_to_run": [],
    }
