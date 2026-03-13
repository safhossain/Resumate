from __future__ import annotations

import json
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Models

MODELS: dict[str, dict] = {
    # Anthropic Claude
    "claude/sonnet-4.6":    {"provider": "claude",   "model_id": "claude-sonnet-4-6"},
    "claude/opus-4.6":      {"provider": "claude",   "model_id": "claude-opus-4-6"},
    # OpenAI
    "openai/gpt-5.4":       {"provider": "openai",   "model_id": "gpt-5.4"},
    # Google Gemini
    "gemini/gemini-3-flash": {"provider": "gemini",  "model_id": "gemini-3-flash-preview"},
    # DeepSeek
    "deepseek/chat":         {"provider": "deepseek", "model_id": "deepseek-chat"},
    # xAI Grok
    "xai/grok-3":            {"provider": "xai",      "model_id": "grok-3"},
}

# Claude


def _claude_ask(model_id: str, prompt: str, system: Optional[str]) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict = {
        "model": model_id,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    text_block = next(b for b in msg.content if b.type == "text")
    return text_block.text


def _claude_ask_json(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict = {
        "model": model_id,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    text_block = next(b for b in msg.content if b.type == "text")
    return json.loads(text_block.text)


# OpenAI-compatible (OpenAI + xAI share the same interface)


def _openai_ask(
    model_id: str,
    api_key: str,
    base_url: Optional[str],
    prompt: str,
    system: Optional[str],
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(model=model_id, messages=messages)
    return resp.choices[0].message.content or ""


def _openai_ask_json(
    model_id: str,
    api_key: str,
    base_url: Optional[str],
    prompt: str,
    schema: dict,
    system: Optional[str],
) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=model_id,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": schema},
        },
    )
    return json.loads(resp.choices[0].message.content or "")


# Gemini


def _gemini_ask(model_id: str, prompt: str, system: Optional[str]) -> str:
    import google.genai as genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = genai_types.GenerateContentConfig(
        system_instruction=system,
    )
    resp = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return resp.text or ""


def _gemini_ask_json(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> dict:
    import google.genai as genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=schema,
        system_instruction=system,
    )
    resp = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return json.loads(resp.text or "")


# DeepSeek
# DeepSeek supports json_object but not json_schema, so the schema is
# serialised into the system prompt and validated client-side (with retries).


def _deepseek_ask(model_id: str, prompt: str, system: Optional[str]) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(model=model_id, messages=messages)
    return resp.choices[0].message.content or ""


def _deepseek_ask_json(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
    schema_str = json.dumps(schema, indent=2)
    schema_instruction = (
        f"Return valid JSON that strictly conforms to this schema:\n{schema_str}\n\nReturn ONLY JSON, no extra text."
    )
    sys_content = f"{system}\n\n{schema_instruction}" if system else schema_instruction

    last_content: Optional[str] = None
    for _ in range(3):
        resp = client.chat.completions.create(
            model=model_id,
            max_tokens=4096,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_content},
                {"role": "user", "content": prompt},
            ],
        )
        content = resp.choices[0].message.content
        last_content = content
        if not content or not content.strip():
            continue
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            continue

    raise RuntimeError(
        f"DeepSeek returned invalid JSON after 3 attempts. Last response: {last_content!r}"
    )


# Routing helpers


def _resolve(model: str) -> tuple[str, str]:
    """Return (provider, model_id) for a model key, or raise ValueError."""
    if model not in MODELS:
        raise ValueError(f"Unknown model {model!r}. Available models: {list(MODELS)}")
    entry = MODELS[model]
    return entry["provider"], entry["model_id"]


# Public API


def ask(model: str, prompt: str, system: Optional[str] = None) -> str:
    """Send *prompt* to *model* and return the plain-text response.

    Args:
        model:  A key from MODELS, e.g. ``"claude/sonnet-4.6"``.
        prompt: The user message to send.
        system: Optional system prompt / persona instruction.

    Returns:
        The model's response as a plain string.

    Raises:
        ValueError: If *model* is not in MODELS.
        KeyError:   If the required API key env var is not set.
    """
    provider, model_id = _resolve(model)

    if provider == "claude":
        return _claude_ask(model_id, prompt, system)
    if provider == "openai":
        return _openai_ask(model_id, os.environ["OPENAI_API_KEY"], None, prompt, system)
    if provider == "gemini":
        return _gemini_ask(model_id, prompt, system)
    if provider == "deepseek":
        return _deepseek_ask(model_id, prompt, system)
    if provider == "xai":
        return _openai_ask(model_id, os.environ["XAI_API_KEY"], "https://api.x.ai/v1", prompt, system)

    raise ValueError(f"Unhandled provider: {provider!r}")


def ask_json(model: str, prompt: str, schema: dict, system: Optional[str] = None) -> dict:
    """Send *prompt* to *model* and return the response as a parsed dict.

    Args:
        model:  A key from MODELS, e.g. ``"openai/gpt-5.4"``.
        prompt: The user message to send.
        schema: A JSON Schema dict describing the expected response shape.
        system: Optional system prompt / persona instruction.

    Returns:
        Parsed ``dict`` whose structure matches *schema*.

    Raises:
        ValueError:   If *model* is not in MODELS.
        KeyError:     If the required API key env var is not set.
        RuntimeError: If DeepSeek fails to return valid JSON after retries.
    """
    provider, model_id = _resolve(model)

    if provider == "claude":
        return _claude_ask_json(model_id, prompt, schema, system)
    if provider == "openai":
        return _openai_ask_json(model_id, os.environ["OPENAI_API_KEY"], None, prompt, schema, system)
    if provider == "gemini":
        return _gemini_ask_json(model_id, prompt, schema, system)
    if provider == "deepseek":
        return _deepseek_ask_json(model_id, prompt, schema, system)
    if provider == "xai":
        return _openai_ask_json(model_id, os.environ["XAI_API_KEY"], "https://api.x.ai/v1", prompt, schema, system)

    raise ValueError(f"Unhandled provider: {provider!r}")


# Class-based convenience wrapper


class AIGateway:
    """Gateway bound to a single model (and optional system prompt).

    Useful when the same model + persona will be called repeatedly, so you
    don't repeat the model key and system prompt on every call.

    Usage::

        gw = AIGateway(
            model="claude/sonnet-4.6",
            system="You are a concise assistant.",
        )
        text = gw.ask("What is 2 + 2?")
        data = gw.ask_json(
            "Classify the sentiment",
            schema={
                "type": "object",
                "properties": {"sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]}},
                "required": ["sentiment"],
                "additionalProperties": False,
            },
        )
    """

    def __init__(self, model: str, system: Optional[str] = None):
        if model not in MODELS:
            raise ValueError(f"Unknown model {model!r}. Available models: {list(MODELS)}")
        self.model = model
        self.system = system

    def ask(self, prompt: str) -> str:
        """Plain-text request.  See module-level ``ask()`` for full docs."""
        return ask(self.model, prompt, self.system)

    def ask_json(self, prompt: str, schema: dict) -> dict:
        """Structured JSON request.  See module-level ``ask_json()`` for full docs."""
        return ask_json(self.model, prompt, schema, self.system)

    def __repr__(self) -> str:
        return f"AIGateway(model={self.model!r})"
