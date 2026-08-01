"""LLM backends for optional agent phrasing / API path.

Primary decision path runs inside **Grok Build** (session + subagents).
This package provides an optional xAI API client for scripts/tests.
"""

from .grok_client import GrokLLM, get_grok_llm, grok_available

__all__ = ["GrokLLM", "get_grok_llm", "grok_available"]
