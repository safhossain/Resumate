import os
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.shared_params import ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema

load_dotenv()

MODEL_NAME = "grok-3"
BASE_URL = "https://api.x.ai/v1"

JSON_SCHEMA: JSONSchema = {
    "name": "model_status_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "model_name": {"type": "string", "enum": [MODEL_NAME]},
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


def simple_mode():
    client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url=BASE_URL)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": f"Hello {MODEL_NAME}, how are you? Firstly, echo back my original message and then answer the question"}],
    )
    print(response.choices[0].message.content or "")


def json_mode():
    client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url=BASE_URL)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        response_format=ResponseFormatJSONSchema(
            type="json_schema",
            json_schema=JSON_SCHEMA,
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"You are {MODEL_NAME}. Fill every field in the provided schema. "
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
    parser = argparse.ArgumentParser(description=f"Test xAI {MODEL_NAME} API")
    parser.add_argument(
        "--mode",
        choices=["simple", "json"],
        default="simple",
        help="simple: plain greeting | json: structured JSON response",
    )
    args = parser.parse_args()

    if args.mode == "simple":
        simple_mode()
    else:
        json_mode()
