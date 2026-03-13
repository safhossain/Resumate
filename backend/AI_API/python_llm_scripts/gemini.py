import os
import json
import argparse
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()

MODEL_NAME = "gemini-3-flash-preview"

JSON_SCHEMA = {
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
}


def get_client():
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def simple_mode():
    client = get_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=f"Hello {MODEL_NAME}, how are you? Firstly, echo back my original message and then answer the question"
    )
    print(response.text or "")


def json_mode():
    client = get_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=(
            f"You are {MODEL_NAME}. Return your response using the provided JSON schema. "
            "Use your exact model name for model_name, a short current status string for "
            "status, a friendly one-sentence greeting for greeting, and exactly three short "
            "capability strings for capabilities."
        ),
        config={
            "response_mime_type": "application/json",
            "response_json_schema": JSON_SCHEMA,
        },
    )
    data = json.loads(response.text or "")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Test {MODEL_NAME} API")
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
