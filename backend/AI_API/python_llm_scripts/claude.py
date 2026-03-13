import os
import json
import argparse
from dotenv import load_dotenv
import anthropic

load_dotenv()

MODELS = {
    "sonnet-4.6": "claude-sonnet-4-6",
    "opus-4.6": "claude-opus-4-6",
}

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "model_name": {"type": "string"},
        "status": {"type": "string"},
        "greeting": {"type": "string"},
        "capabilities": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["model_name", "status", "greeting", "capabilities"],
    "additionalProperties": False,
}


def simple_mode(model_id: str, model_label: str):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=model_id,
        max_tokens=1024,
        messages=[{"role": "user", "content": f"Hello {model_label}, how are you? Firstly, echo back my original message and then answer the question"}],
    )
    text_block = next(b for b in message.content if b.type == "text")
    print(text_block.text)


def json_mode(model_id: str, model_label: str):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=model_id,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"You are {model_label}. Fill in each field: "
                    "model_name (your model name), status (your current status), "
                    "greeting (a friendly greeting), capabilities (3 things you can help with)."
                ),
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": JSON_SCHEMA,
            }
        },
    )
    text_block = next(b for b in message.content if b.type == "text")
    data = json.loads(text_block.text)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Anthropic Claude models")
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        default="sonnet-4.6",
        help="Which Claude model to test",
    )
    parser.add_argument(
        "--mode",
        choices=["simple", "json"],
        default="simple",
        help="simple: plain greeting | json: structured JSON response",
    )
    args = parser.parse_args()

    model_id = MODELS[args.model]

    if args.mode == "simple":
        simple_mode(model_id, args.model)
    else:
        json_mode(model_id, args.model)
