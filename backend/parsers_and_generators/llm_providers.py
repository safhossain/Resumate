"""
LLM provider implementations.
Each provider returns raw response text; LLM_CALL parses it to LLM_O.
"""
import json
import os
from typing import Optional

from llm_config import PROVIDERS, ProviderId


def _get_key(provider_id: ProviderId) -> Optional[str]:
    cfg = PROVIDERS[provider_id]
    return os.getenv(cfg["env_var"])


def _call_openai_compatible(
    provider_id: ProviderId,
    system: str,
    user: str,
) -> str:
    """OpenAI-compatible API: OpenAI, Groq, DeepSeek."""
    from openai import OpenAI

    cfg = PROVIDERS[provider_id]
    api_key = _get_key(provider_id)
    if not api_key:
        raise ValueError(
            f"Missing {cfg['env_var']} for provider '{provider_id}'. Set it in .env."
        )
    kwargs = {"api_key": api_key}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    client = OpenAI(**kwargs)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    kwargs_create = {
        "model": cfg["model"],
        "messages": messages,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    response = client.chat.completions.create(**kwargs_create)
    return response.choices[0].message.content


def _call_anthropic(system: str, user: str) -> str:
    """Anthropic Claude API."""
    import anthropic

    cfg = PROVIDERS["anthropic"]
    api_key = _get_key("anthropic")
    if not api_key:
        raise ValueError(
            f"Missing {cfg['env_var']} for provider 'anthropic'. Set it in .env."
        )
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=cfg["model"],
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = response.content[0].text
    return text


def _call_gemini(system: str, user: str) -> str:
    """Google Gemini API."""
    import google.generativeai as genai

    cfg = PROVIDERS["gemini"]
    api_key = _get_key("gemini")
    if not api_key:
        raise ValueError(
            f"Missing {cfg['env_var']} for provider 'gemini'. Set it in .env."
        )
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=cfg["model"],
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    response = model.generate_content(user)
    return response.text


def call_provider(provider_id: ProviderId, system: str, user: str) -> str:
    """Dispatch to the correct provider. Returns raw response text."""
    if provider_id in ("openai", "grok", "deepseek"):
        return _call_openai_compatible(provider_id, system, user)
    if provider_id == "anthropic":
        return _call_anthropic(system, user)
    if provider_id == "gemini":
        return _call_gemini(system, user)
    raise ValueError(f"Unknown provider: {provider_id}")
