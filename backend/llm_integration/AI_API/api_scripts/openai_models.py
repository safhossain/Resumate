import os
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.shared_params import ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema

load_dotenv()

MODELS = {
    "gpt-5.4": "gpt-5.4",
    "gpt-5.3-codex": "gpt-5.3-codex",
}

def build_json_schema(model_label: str) -> JSONSchema:
    return {
        "name": "model_status_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "enum": [model_label]},
                "status": {"type": "string"},
                "greeting": {"type": "string"},
                "capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["model_name", "status", "greeting", "capabilities"],
            "additionalProperties": False,
        },
    }


def simple_mode(model_id: str, model_label: str):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": f"Hello {model_label}, how are you? Firstly, echo back my original message and then answer the question"}]
    )
    print(response.choices[0].message.content or "")


def json_mode(model_id: str, model_label: str):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model_id,
        response_format=ResponseFormatJSONSchema(
            type="json_schema",
            json_schema=build_json_schema(model_label),
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"You are {model_label}. Fill every field in the provided schema. "
                    "Use your exact model name for model_name, a short current status "
                    "for status, a friendly one-sentence greeting for greeting, and "
                    "exactly three short capability strings for capabilities."
                ),
            }
        ],
    )
    data = json.loads(response.choices[0].message.content or "")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test OpenAI GPT models")
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        default="gpt-5.4",
        help="Which OpenAI model to test",
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
