"""
LLM provider configuration.
Env vars (set in .env): OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY, DEEPSEEK_KEY
"""
from typing import Literal

ProviderId = Literal["openai", "anthropic", "gemini", "grok", "deepseek"]

PROVIDERS: dict[ProviderId, dict] = {
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "base_url": None,  # default OpenAI URL
        "model": "gpt-4o",
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": None,
        "model": "claude-sonnet-4-20250514",
    },
    "gemini": {
        "env_var": "GOOGLE_API_KEY",
        "base_url": None,
        "model": "gemini-1.5-pro",
    },
    "grok": {
        "env_var": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "model": "grok-4-1-fast-reasoning",
    },
    "deepseek": {
        "env_var": "DEEPSEEK_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
}

DEFAULT_PROVIDER: ProviderId = "deepseek"
