"""
xAI / Grok LLM client (OpenAI-compatible API).

Env:
  XAI_API_KEY   — required for API calls
  XAI_BASE_URL  — default https://api.x.ai/v1
  XAI_MODEL     — default grok-4.5

Used for optional quant debate rephrase and scripted paths.
Primary multi-agent decisions run in Grok Build (not this client).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4.5"


def grok_available() -> bool:
    return bool(os.environ.get("XAI_API_KEY", "").strip())


def get_grok_llm(
    model: Optional[str] = None,
    *,
    require_key: bool = False,
) -> Optional["GrokLLM"]:
    """Return GrokLLM if XAI_API_KEY is set, else None (or raise if require_key)."""
    if not grok_available():
        if require_key:
            raise RuntimeError(
                "XAI_API_KEY is not set. Export it to use the Grok API client. "
                "For Grok Build multi-agent decisions, use /decide-stock instead."
            )
        return None
    return GrokLLM(model=model or os.environ.get("XAI_MODEL", DEFAULT_MODEL))


@dataclass
class _Content:
    content: str


class GrokLLM:
    """Minimal chat client with LangChain-like .invoke(prompt) -> object.content."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        timeout_s: float = 120.0,
    ):
        self.model = model or os.environ.get("XAI_MODEL", DEFAULT_MODEL)
        self.api_key = (api_key or os.environ.get("XAI_API_KEY") or "").strip()
        self.base_url = (base_url or os.environ.get("XAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.temperature = temperature
        self.timeout_s = timeout_s
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY required for GrokLLM")

    def invoke(self, prompt: str) -> _Content:
        text = self.chat(str(prompt))
        return _Content(content=text)

    def __call__(self, prompt: str) -> _Content:
        return self.invoke(prompt)

    def chat(self, prompt: str, *, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat_messages(messages)

    def chat_messages(self, messages: list) -> str:
        # Prefer official openai package when installed
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except ImportError:
            pass

        return self._chat_urllib(messages)

    def _chat_urllib(self, messages: list) -> str:
        url = f"{self.base_url}/chat/completions"
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Grok API HTTP {e.code}: {err}") from e
        except Exception as e:
            raise RuntimeError(f"Grok API request failed: {e}") from e

        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected Grok API response shape: {data!r}") from e
