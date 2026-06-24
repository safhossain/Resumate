from __future__ import annotations
import json
import os
from typing import Optional
from dotenv import load_dotenv

import anthropic
from openai import OpenAI
import google.genai as genai
from google.genai import types as genai_types

from .contracts import LLM_I, LLM_O

load_dotenv()

MODELS: dict[str, dict] = {
    "claude/sonnet-4.6":    {"provider": "claude",   "model_id": "claude-sonnet-4-6"},
    "claude/opus-4.6":      {"provider": "claude",   "model_id": "claude-opus-4-6"},
    "openai/gpt-5.4":       {"provider": "openai",   "model_id": "gpt-5.4"},
    "gemini/gemini-3-flash": {"provider": "gemini",  "model_id": "gemini-3-flash-preview"},
    "deepseek/chat":         {"provider": "deepseek", "model_id": "deepseek-chat"},
    "xai/grok-3":            {"provider": "xai",      "model_id": "grok-3"},
}


def _build_messages(system: Optional[str], prompt: str) -> list[dict]:
    """Build the standard chat messages list (optional system + user prompt)."""
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _claude_ask(model_id: str, prompt: str, system: Optional[str]) -> str:
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

def _claude_ask_json(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> LLM_O:
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

    client = OpenAI(api_key=api_key, base_url=base_url)
    messages = _build_messages(system, prompt)
    resp = client.chat.completions.create(model=model_id, messages=messages)
    return resp.choices[0].message.content or ""

def _openai_ask_json(
    model_id: str,
    api_key: str,
    base_url: Optional[str],
    prompt: str,
    schema: dict,
    system: Optional[str],
) -> LLM_O:
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    messages = _build_messages(system, prompt)
    resp = client.chat.completions.create(
        model=model_id,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": schema},
        },
    )
    return json.loads(resp.choices[0].message.content or "")


def _gemini_ask(model_id: str, prompt: str, system: Optional[str]) -> str:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = genai_types.GenerateContentConfig(
        system_instruction=system,
    )
    resp = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return resp.text or ""

def _gemini_ask_json(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> LLM_O:
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
    messages = _build_messages(system, prompt)
    resp = client.chat.completions.create(model=model_id, messages=messages)
    return resp.choices[0].message.content or ""

def _deepseek_ask_json(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> LLM_O:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
    schema_str = json.dumps(schema, indent=2)
    schema_instruction = (
        f"Return valid JSON that strictly conforms to this schema:\n{schema_str}\n\nReturn ONLY JSON, no extra text."
    )
    sys_content = f"{system}\n\n{schema_instruction}" if system else schema_instruction
    messages = _build_messages(sys_content, prompt)

    last_content: Optional[str] = None
    for _ in range(3):
        resp = client.chat.completions.create(
            model=model_id,
            max_tokens=4096,
            response_format={"type": "json_object"},
            messages=messages,
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

## Local LLM
def _ollama_llm_ask(model_id: str, prompt: str, system: Optional[str]) -> str:
    from ollama import chat

    response = chat(model=model_id, messages=_build_messages(system, prompt))
    return response["message"]["content"] or ""


def _ollama_llm_ask_json(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> LLM_O:
    from ollama import chat

    response = chat(model=model_id, messages=_build_messages(system, prompt), format=schema)
    return json.loads(response["message"]["content"] or "")



# Provider registry
# OpenAI and xAI speak the same wire protocol, differing only in the API-key
# env var and base URL. The env var is read lazily (inside the closures) so
# importing this module never requires keys for providers you don't use.
def _make_openai_text(env_var: str, base_url: Optional[str]):
    def handler(model_id: str, prompt: str, system: Optional[str]) -> str:
        return _openai_ask(model_id, os.environ[env_var], base_url, prompt, system)
    return handler


def _make_openai_json(env_var: str, base_url: Optional[str]):
    def handler(model_id: str, prompt: str, schema: dict, system: Optional[str]) -> LLM_O:
        return _openai_ask_json(model_id, os.environ[env_var], base_url, prompt, schema, system)
    return handler


# provider -> (text_handler, json_handler)
#   text_handler(model_id, prompt, system) -> str
#   json_handler(model_id, prompt, schema, system) -> LLM_O
_PROVIDERS: dict[str, tuple] = {
    "claude":   (_claude_ask, _claude_ask_json),
    "openai":   (_make_openai_text("OPENAI_API_KEY", None),
                 _make_openai_json("OPENAI_API_KEY", None)),
    "xai":      (_make_openai_text("XAI_API_KEY", "https://api.x.ai/v1"),
                 _make_openai_json("XAI_API_KEY", "https://api.x.ai/v1")),
    "gemini":   (_gemini_ask, _gemini_ask_json),
    "deepseek": (_deepseek_ask, _deepseek_ask_json),
    "ollama":   (_ollama_llm_ask, _ollama_llm_ask_json),
}


# Routing helpers
def _resolve(model: str) -> tuple[str, str]:
    """
    Local Models are only supported using Ollama
    Return (provider, model_id) for a model key, or raise ValueError.
    """
    if "ollama" in model:
        return "ollama", model.replace("ollama","").replace("/", "").strip()

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
    handlers = _PROVIDERS.get(provider)
    if handlers is None:
        raise ValueError(f"Unhandled provider: {provider!r}")
    text_handler, _ = handlers
    return text_handler(model_id, prompt, system)

def ask_json(model: str, prompt: str, schema: dict, system: Optional[str] = None) -> LLM_O:
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
    handlers = _PROVIDERS.get(provider)
    if handlers is None:
        raise ValueError(f"Unhandled provider: {provider!r}")
    _, json_handler = handlers
    return json_handler(model_id, prompt, schema, system)


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

    def ask_json(self, prompt: str, schema: dict) -> LLM_O:
        """Structured JSON request.  See module-level ``ask_json()`` for full docs."""
        return ask_json(self.model, prompt, schema, self.system)

    def __repr__(self) -> str:
        return f"AIGateway(model={self.model!r})"
