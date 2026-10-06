import json
from unittest.mock import Mock, patch

import httpx2 as httpx
import pytest
import requests
from openai import RateLimitError

from backend.app import developer_llm as llm
from backend.app.developer_copilot import analyze_developer_request
from backend.app.llm_analyzer import analyze_with_llm


VALID = {
    "summary": "Import failed.", "reasoning": "An import error was observed.",
    "recommended_fix": "Inspect dependencies.", "code_change_available": False,
    "code_change_summary": "Review dependencies first.", "tests_to_run": ["Validate DAG import."],
}


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in (
        "LLM_PROVIDER", "LLM_FALLBACK_PROVIDERS", "GEMINI_API_KEY", "GEMINI_MODEL",
        "OPENAI_API_KEY", "OPENAI_MODEL", "DEVELOPER_COPILOT_MODEL",
        "OLLAMA_BASE_URL", "OLLAMA_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    with patch.object(llm.requests, "post", side_effect=AssertionError("Unexpected network")), patch.object(
        llm, "OpenAI", side_effect=AssertionError("Unexpected OpenAI call")
    ):
        yield


def analyze():
    return llm.analyze_with_developer_llm(
        "Why?", "import_error", "broken.py", ["Import failed"], "DAG Parsing", None, "Inspect imports."
    )


def gemini_response(output):
    return Mock(json=lambda: {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": output}]}}]})


def test_gemini_request(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch.object(llm.requests, "post", return_value=gemini_response(json.dumps(VALID))) as post:
        assert analyze() == {**VALID, "status": "success"}
    assert "gemini-2.5-flash:generateContent" in post.call_args.args[0]
    assert post.call_args.kwargs["headers"] == {"x-goog-api-key": "test-key"}
    assert post.call_args.kwargs["timeout"] == (5, 30)
    assert "responseJsonSchema" in post.call_args.kwargs["json"]["generationConfig"]


def test_ollama_request(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "local-model")
    with patch.object(llm.requests, "post", return_value=Mock(json=lambda: {
        "done": True, "message": {"content": json.dumps(VALID)}
    })) as post:
        assert analyze()["status"] == "success"
    assert post.call_args.args[0] == "http://localhost:11434/api/chat"
    assert post.call_args.kwargs["json"]["stream"] is False
    assert post.call_args.kwargs["json"]["format"]["type"] == "object"


def test_legacy_openai_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEVELOPER_COPILOT_MODEL", "copilot-model")
    with patch.object(llm, "OpenAI") as client:
        create = client.return_value.__enter__.return_value.responses.create
        create.return_value.output_text = json.dumps(VALID)
        assert analyze()["status"] == "success"
        assert create.call_args.kwargs["model"] == "copilot-model"
        assert client.call_args.kwargs["max_retries"] == 0


def test_quota_exception_preserves_evidence(monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    error = RateLimitError("secret-provider-message", response=response, body={"code": "credit_balance_exhausted"})
    with patch.object(llm, "OpenAI") as client:
        client.return_value.__enter__.return_value.responses.create.side_effect = error
        result = analyze()
    assert result["status"] == "provider_unavailable"
    assert result["recommended_fix"] == "Inspect imports."
    assert result["code_change_available"] is False
    assert "secret-provider-message" not in caplog.text


@pytest.mark.parametrize("output", ["not JSON", "[]", "null", "{}", json.dumps({**VALID, "code_change_available": "false"}), json.dumps({**VALID, "tests_to_run": "run tests"})])
def test_invalid_output(monkeypatch, output):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch.object(llm.requests, "post", return_value=gemini_response(output)):
        assert analyze()["status"] == "invalid_llm_response"


def test_fallback_order(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_MODEL", "local-model")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "ollama,gemini,ollama")
    with patch.object(llm.requests, "post", side_effect=[requests.Timeout(), Mock(json=lambda: {
        "done": True, "message": {"content": json.dumps(VALID)}
    })]) as post:
        assert analyze()["status"] == "success"
    assert post.call_count == 2
    assert "googleapis" in post.call_args_list[0].args[0]
    assert "localhost" in post.call_args_list[1].args[0]


@pytest.mark.parametrize("provider", ["gemini", "ollama", "openai", "typo", "none"])
def test_missing_configuration(monkeypatch, provider):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    assert analyze()["status"] == "not_configured"


def test_hybrid_uses_same_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    payload = {
        "incident_class": "DAG Parsing", "confidence": 0.8, "reasoning": "Import error.",
        "supporting_evidence": ["Import failed"], "l1_checks": ["Check dependencies"],
        "escalation_needed": True, "escalation_reason": "Review imports",
    }
    with patch.object(llm.requests, "post", return_value=gemini_response(json.dumps(payload))):
        assert analyze_with_llm({"error": "Import failed"}) == {**payload, "status": "success"}


def test_copilot_evidence_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("backend.app.developer_copilot.AirflowAdapter") as adapter, patch.object(
        llm.requests, "post", side_effect=requests.ConnectionError()
    ):
        adapter.return_value.get_import_error.return_value = {
            "filename": "broken.py", "stack_trace": "ModuleNotFoundError: missing_module"
        }
        result = analyze_developer_request("Why?", "import_error", import_error_id="123")
    assert result.status == "success"
    assert result.diagnosis.incident_class == "DAG Parsing"
    assert "unavailable" in result.reasoning
    assert result.evidence and result.tests_to_run and result.recommended_fix
    assert result.human_review_required is True
    assert result.code_change.available is False


@pytest.mark.parametrize("payload", [{}, {"candidates": []}, {"candidates": [None]}, {"candidates": [{"finishReason": "MAX_TOKENS"}]}])
def test_bad_provider_envelope(monkeypatch, payload):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch.object(llm.requests, "post", return_value=Mock(json=lambda: payload)):
        assert analyze()["status"] == "invalid_llm_response"


def test_all_providers_down(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_MODEL", "local-model")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "ollama")
    with patch.object(llm.requests, "post", side_effect=requests.ConnectionError()) as post:
        assert analyze_with_llm({})["status"] == "provider_unavailable"
    assert post.call_count == 2


@pytest.mark.parametrize("incident_type", ["dag", "import_error"])
def test_chat_endpoint_survives_quota_failure(monkeypatch, incident_type, tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.evidence import AirflowEvidence
    from backend.app.incident_evidence import IncidentEvidence
    from backend.app.main import app
    from backend.app import source_resolver

    monkeypatch.setattr(source_resolver, "DAG_SOURCE_ROOT", tmp_path)
    (tmp_path / "support_intelligence_supervisor_demo.py").write_text(
        "def supervisor_demo_incident(**context):\n    raise RuntimeError('Synthetic failure')\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    error = RateLimitError("No credits remaining", response=response, body={"code": "credit_balance_exhausted"})
    with patch("backend.app.developer_copilot.AirflowAdapter") as adapter, patch(
        "backend.app.developer_copilot.analyze_airflow_with_ml",
        return_value={"status": "success", "incident_class": "Resource", "confidence": 0.8},
    ), patch.object(llm, "OpenAI") as provider:
        adapter.return_value.get_incident_evidence.return_value = IncidentEvidence(
            airflow=AirflowEvidence(latest_dag_run_state="failed", failed_task_count=1), kubernetes=None,
        )
        adapter.return_value.get_import_error.return_value = {
            "filename": "broken.py", "stack_trace": "ModuleNotFoundError: missing_module"
        }
        create = provider.return_value.__enter__.return_value.responses.create
        create.side_effect = error
        body = {"message": "Why did this fail?", "incident_type": incident_type}
        if incident_type == "dag":
            body["dag_id"] = "support_intelligence_supervisor_demo"
        else:
            body["import_error_id"] = "123"
        result = TestClient(app).post("/developer/chat", json=body)
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "success"
    assert payload["evidence"] and payload["tests_to_run"]
    assert "unavailable" in payload["reasoning"]
    assert payload["human_review_required"] is True
    assert create.call_count == (2 if incident_type == "dag" else 1)
    if incident_type == "dag":
        assert payload["diagnosis"]["incident_class"] == "Resource"
        assert payload["code_change"]["available"] is False
        assert payload["code_change"]["generated_by"] == "no_proposal"
