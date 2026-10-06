# LLM provider setup

Both Developer Copilot and the hybrid incident analyzer use the provider layer
in `backend/app/developer_llm.py`. Their prompts and public response contracts
remain separate. ML, Kubernetes evidence, policy, and controlled source changes
continue through the existing pipeline.

The configured account was verified on 2026-10-05 with `gemini-3.5-flash-lite`:
real structured AI proposal succeeded. The old `gemini-2.5-flash` generation request
returned HTTP 404 (`NOT_FOUND`: unavailable to new users), despite metadata
being available. `gemini-3.8-flash` returned high-demand 503s and `gemini-3.7-flash`
timed out. Model discovery does not guarantee generation access or capacity.
See [the exact live result](general-ai-remediation.md). Explicit `GEMINI_MODEL`
configuration takes precedence over the legacy code default.

## Gemini demo setup (PowerShell, project root)

```powershell
.venv/Scripts/python.exe -m pip install "python-dotenv>=1.0,<2"
Copy-Item .env.example .env
```

Edit `.env` locally and add your Gemini API key:

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
LLM_FALLBACK_PROVIDERS=
```

Get a key from [Google AI Studio](https://aistudio.google.com/apikey). Model
availability and free-tier quotas depend on your account; check Google's
[pricing](https://ai.google.dev/gemini-api/docs/pricing). This configuration
does not guarantee free or unlimited requests.

Stop the old backend, then restart it from the project root:

```powershell
.venv/Scripts/python.exe -m uvicorn backend.app.main:app --reload --env-file .env
```

The `--env-file` flag is required to load the file. Existing environment variables
override `.env`; clear any stale provider/model variables in the launching shell.
Restart the backend after configuration changes. `.env` is ignored by Git.

Alternatively, use `$env:LLM_PROVIDER = "gemini"`, `$env:GEMINI_API_KEY = "..."`,
and `$env:GEMINI_MODEL = "gemini-3.5-flash-lite"` in the launching PowerShell session
and start Uvicorn without `--env-file` (no dotenv installation needed).

Test with a real DAG ID from your Airflow instance:

```powershell
$body = @{
    message = "Why is this DAG failing?"
    incident_type = "dag"
    dag_id = "YOUR_EXISTING_DAG_ID"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/developer/chat" -ContentType "application/json" -Body $body
```

For an import error, use `incident_type = "import_error"` and
`import_error_id = "YOUR_IMPORT_ERROR_ID"` instead of `dag_id`.

## Ollama

Start Ollama and pull a model suitable for your machine. Set `OLLAMA_MODEL` to
the exact installed tag shown by `ollama list`; model quality and latency need
to be measured on your hardware.

```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=your-installed-model-tag
```

For Gemini first, then Ollama, set `LLM_PROVIDER=gemini` and
`LLM_FALLBACK_PROVIDERS=ollama`, keeping the Ollama settings above. Leave fallback
providers empty until the local server/model is ready.

## OpenAI and offline mode

`LLM_PROVIDER=openai` uses `OPENAI_API_KEY` and `OPENAI_MODEL`. The existing
`DEVELOPER_COPILOT_MODEL` override still takes precedence for Copilot only.
If `LLM_PROVIDER` is unset, OpenAI remains the legacy default.
`LLM_PROVIDER=none` disables all LLM requests, including configured fallbacks.

## Failure behavior

Each provider is attempted once, in configured order. No automatic cloud
fallback occurs unless explicitly listed. Missing keys/models, quota errors,
connection failures, blocked/truncated responses, and invalid structured output
fall back to the next configured provider, then existing evidence/ML reasoning.
Cloud calls have a 30-second read timeout; Ollama has 60 seconds for local
generation (HTTP connect timeout: 5 seconds). DAG investigations can make two
LLM calls: hybrid classification and developer explanation.

The endpoint keeps its existing response shape. When Copilot falls back,
`reasoning` says developer-specific LLM reasoning is unavailable, while the
diagnosis, evidence, conservative recommendation, and validation steps remain.
Backend warnings identify the failing provider and exception type without
logging keys, prompts, or raw error bodies. HTTP success alone does not prove
that an LLM answered. Airflow/evidence retrieval failures remain real errors.

LLM output never executes actions or enables a source patch. Existing controlled
source proposals and human review continue unchanged.

Provider interfaces: [Gemini generateContent](https://ai.google.dev/api/generate-content),
[Ollama chat](https://docs.ollama.com/api/chat),
[OpenAI errors](https://developers.openai.com/api/docs/guides/error-codes).

## Offline regression tests

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_llm_providers.py tests/test_developer_copilot.py tests/test_hybrid_analyzer.py -q -p no:cacheprovider
```

Provider calls are mocked; these tests require no credits, keys, or local model.
