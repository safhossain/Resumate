import json
import argparse
import ollama

MODEL_NAME = "qwen2.5:14b"

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "model_name": {"type": "string", "enum": [MODEL_NAME]},
        "status": {"type": "string"},
        "greeting": {"type": "string"},
        "capabilities": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
    },
    "required": ["model_name", "status", "greeting", "capabilities"],
    "additionalProperties": False,
}


def simple_mode():
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Hello {MODEL_NAME}, how are you? "
                    "Firstly, echo back my original message and then answer the question."
                ),
            }
        ],
    )

    print(response["message"]["content"])


def json_mode():
    prompt = (
        f"You are {MODEL_NAME}. Return your response using the provided JSON schema.\n"
        f"Use your exact model name for model_name.\n"
        f"Use a short current status string for status.\n"
        f"Use a friendly one-sentence greeting for greeting.\n"
        f"Use exactly three short capability strings for capabilities.\n\n"
        "Return ONLY valid JSON.\n"
        "Do not include markdown fences.\n"
        "Do not include explanations.\n\n"
        f"Schema:\n{json.dumps(JSON_SCHEMA, indent=2)}"
    )

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )

    text = response["message"]["content"]

    data = json.loads(text)

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Test local Ollama model: {MODEL_NAME}")
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