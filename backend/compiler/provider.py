"""Real OpenAI-compatible inference, with no mock or fallback provider."""

import json
import os
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values


class CompilerError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class LLMProvider(Protocol):
    model: str

    def generate(self, system_prompt: str, user_payload: dict) -> str: ...


class OpenAICompatibleProvider:
    timeout_seconds = 90

    def __init__(self, base_url: str, api_key: str, model: str,
                 *, transport: httpx.BaseTransport | None = None):
        try:
            parsed = urlsplit(base_url)
            parsed.port  # Validate malformed/out-of-range ports before constructing a request.
        except ValueError:
            raise CompilerError(503, "SHADOWOPS_LLM_BASE_URL is not a valid HTTPS API base URL.") from None
        local_http = parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")
        if (not (parsed.scheme == "https" or local_http) or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise CompilerError(503, "SHADOWOPS_LLM_BASE_URL must be an HTTPS API base URL, or HTTP on 127.0.0.1/localhost, without credentials, query or fragment.")
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self._api_key = api_key
        self._transport = transport

    @classmethod
    def from_environment(cls, env_file: Path | None = None):
        env_file = env_file or Path(__file__).resolve().parents[1] / ".env"
        # Environment variables win; read only this backend's ignored .env file.
        try:
            values = dotenv_values(env_file, encoding="utf-8-sig", interpolate=False)
        except (OSError, UnicodeError):
            raise CompilerError(503, "Cannot read backend/.env. Use UTF-8 or configure environment variables.") from None
        names = ("SHADOWOPS_LLM_BASE_URL", "SHADOWOPS_LLM_API_KEY", "SHADOWOPS_LLM_MODEL")
        settings = {name: os.environ.get(name, values.get(name) or "").strip() for name in names}
        missing = [name for name in names if not settings[name]]
        if missing:
            raise CompilerError(503, "LLM is not configured. Missing: " + ", ".join(missing))
        provider_name = os.environ.get("SHADOWOPS_LLM_PROVIDER", values.get("SHADOWOPS_LLM_PROVIDER") or "openai").strip()
        if provider_name not in ("openai", "ollama"):
            raise CompilerError(503, "SHADOWOPS_LLM_PROVIDER must be openai or ollama.")
        provider_class = OllamaCompatibleProvider if provider_name == "ollama" else cls
        return provider_class(*(settings[name] for name in names))

    def _request_body(self, system_prompt: str, user_payload: dict) -> dict:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))},
            ],
            "response_format": {"type": "json_object"},
        }

    def _read_content(self, message: dict) -> str:
        content = message["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Missing JSON content")
        return content

    def generate(self, system_prompt: str, user_payload: dict) -> str:
        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds, connect=10), follow_redirects=False,
                              transport=self._transport) as client:
                response = client.post(
                    self.endpoint,
                    headers={"Authorization": "Bearer " + self._api_key},
                    json=self._request_body(system_prompt, user_payload),
                )
        except httpx.TimeoutException:
            raise CompilerError(504, "LLM request timed out. No draft was saved.") from None
        except (httpx.HTTPError, httpx.InvalidURL):
            raise CompilerError(503, "LLM connection failed. Check the API base URL and network.") from None
        if response.status_code in (401, 403):
            raise CompilerError(503, "LLM credentials were rejected by the provider.")
        if response.status_code == 429:
            raise CompilerError(503, "LLM provider rate or quota limit reached. Try again later.")
        if response.status_code != 200:
            # Do not expose upstream bodies; they can contain credentials or prompts.
            raise CompilerError(502, f"LLM provider returned HTTP {response.status_code}. Check model and Chat Completions JSON-mode support.")
        try:
            if len(response.content) > 1_000_000:
                raise ValueError("Response too large")
            choice = response.json()["choices"][0]
            if not isinstance(choice, dict):
                raise ValueError("Invalid choice")
            message = choice["message"]
            if not isinstance(message, dict):
                raise ValueError("Invalid message")
            if choice.get("finish_reason") != "stop" or message.get("refusal") or message.get("tool_calls"):
                raise ValueError("Incomplete or refused response")
            return self._read_content(message)
        except (ValueError, KeyError, IndexError, TypeError):
            raise CompilerError(502, "LLM returned an incomplete, refused or malformed response. No draft was saved.") from None


class OllamaCompatibleProvider(OpenAICompatibleProvider):
    """Local Ollama's OpenAI API; the cloud provider's behavior stays unchanged."""

    timeout_seconds = 300

    def __init__(self, base_url: str, api_key: str, model: str, **kwargs):
        super().__init__(base_url, api_key, model, **kwargs)
        if urlsplit(base_url).hostname not in ("127.0.0.1", "localhost"):
            raise CompilerError(503, "The ollama provider is restricted to 127.0.0.1/localhost. Use openai for a remote cloud provider.")

    def _request_body(self, system_prompt: str, user_payload: dict) -> dict:
        body = super()._request_body(system_prompt, user_payload)
        body.update(reasoning_effort="none", temperature=0, max_tokens=8192)
        schema = user_payload.get("skill_draft_json_schema")
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "skill_draft", "strict": True, "schema": schema},
            }
        return body

    def _read_content(self, message: dict) -> str:
        if message.get("content"):
            return super()._read_content(message)
        # Some Qwen/Ollama versions put the complete JSON answer in reasoning,
        # even with reasoning_effort=none. Accept only a whole JSON object;
        # never extract JSON from prose, repair it, or accept truncated answers.
        content = message.get("reasoning") or message.get("reasoning_content")
        if not isinstance(content, str) or not isinstance(json.loads(content), dict):
            raise ValueError("No complete JSON object")
        return content  # The same strict Pydantic and evidence checks still apply.
