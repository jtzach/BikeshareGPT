from __future__ import annotations

import os
from typing import Callable
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - import is resolved at runtime when the backend is actually used
    OpenAI = None  # type: ignore


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: str
    usage: LLMUsage
    raw: Any = None


class OpenAIChat:
    """Thin wrapper around an OpenAI-compatible chat endpoint.

    We intentionally keep this small and explicit to make runs reproducible.
    The same wrapper works for:
    - OpenAI's hosted API
    - Ollama Cloud's OpenAI-compatible endpoint at https://ollama.com/v1
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        if OpenAI is None:
            raise RuntimeError("The `openai` package is not installed. Install requirements.txt before running the benchmark.")
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        base_url = base_url or os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Put it in .env or environment variables.")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    @staticmethod
    def _prefer_responses_api(model: str) -> bool:
        model = (model or "").lower()
        return model.startswith("gpt-5")

    def _chat_completion(self, *, model: str, messages: List[Dict[str, str]], temperature: float) -> LLMResponse:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        # Some reasoning models are stricter about accepted parameters.
        if not self._prefer_responses_api(model):
            kwargs["temperature"] = temperature
        resp = self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        u = LLMUsage(
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )
        return LLMResponse(content=content, usage=u, raw=resp)

    def _responses_api(self, *, model: str, messages: List[Dict[str, str]], temperature: float) -> LLMResponse:
        kwargs: Dict[str, Any] = {
            "model": model,
            "input": messages,
        }
        if not self._prefer_responses_api(model):
            kwargs["temperature"] = temperature
        resp = self.client.responses.create(**kwargs)

        text = getattr(resp, "output_text", "") or ""
        if not text:
            try:
                for item in getattr(resp, "output", []) or []:
                    if getattr(item, "type", None) == "message":
                        for c in getattr(item, "content", []) or []:
                            ctype = getattr(c, "type", None)
                            if ctype in {"output_text", "text"}:
                                text += getattr(c, "text", "") or ""
            except Exception:
                pass

        usage = getattr(resp, "usage", None)
        u = LLMUsage(
            prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
            completion_tokens=getattr(usage, "output_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )
        return LLMResponse(content=text, usage=u, raw=resp)

    def chat(self, *, model: str, messages: List[Dict[str, str]], temperature: float = 0.0) -> LLMResponse:
        methods: List[Callable[..., LLMResponse]]
        if self._prefer_responses_api(model):
            methods = [self._responses_api, self._chat_completion]
        else:
            methods = [self._chat_completion, self._responses_api]

        last_error: Optional[Exception] = None
        for method in methods:
            try:
                return method(model=model, messages=messages, temperature=temperature)
            except Exception as e:
                last_error = e

        raise RuntimeError(f"All API attempts failed for model '{model}': {last_error}")


def resolve_provider_settings(
    *,
    provider: str,
    api_key_env: Optional[str] = None,
    base_url: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Resolve credentials/base URL for a supported provider.

    Supported providers:
    - openai: uses OPENAI_API_KEY and optional OPENAI_BASE_URL
    - ollama: uses OLLAMA_API_KEY and defaults to https://ollama.com/v1
    """
    provider = provider.lower().strip()
    if provider == "openai":
        env_name = api_key_env or "OPENAI_API_KEY"
        api_key = os.getenv(env_name)
        resolved_base = base_url or os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise RuntimeError(
                f"{env_name} is missing. Put it in .env or environment variables to use the OpenAI backend."
            )
        return api_key, resolved_base

    if provider == "ollama":
        env_name = api_key_env or "OLLAMA_API_KEY"
        api_key = os.getenv(env_name)
        resolved_base = base_url or os.getenv("OLLAMA_BASE_URL") or "https://ollama.com/v1"
        if not api_key:
            raise RuntimeError(
                f"{env_name} is missing. Put it in .env or environment variables to use the Ollama backend."
            )
        return api_key, resolved_base

    raise RuntimeError(f"Unsupported provider: {provider}")


def make_chat_client(
    *,
    provider: str,
    api_key_env: Optional[str] = None,
    base_url: Optional[str] = None,
) -> OpenAIChat:
    api_key, resolved_base = resolve_provider_settings(
        provider=provider,
        api_key_env=api_key_env,
        base_url=base_url,
    )
    return OpenAIChat(api_key=api_key, base_url=resolved_base)
