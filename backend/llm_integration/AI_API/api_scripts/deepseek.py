import os
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL_NAME = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"

JSON_SYSTEM_PROMPT = """Return output in JSON format.

Use exactly this JSON shape:
{
  "model_name": "deepseek-chat",
  "status": "string",
  "greeting": "string",
  "capabilities": ["string", "string", "string"]
}

Return only JSON with those four keys.
"""


def is_valid_payload(data):
    if not isinstance(data, dict):
        return False

    required_keys = {"model_name", "status", "greeting", "capabilities"}
    if set(data.keys()) != required_keys:
        return False

    if not isinstance(data["capabilities"], list) or len(data["capabilities"]) != 3:
        return False

    return all(isinstance(item, str) for item in data["capabilities"])


def simple_mode():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BASE_URL)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": f"Hello {MODEL_NAME}, how are you?. Firstly, echo back my original message and then answer the question."}],
    )
    print(response.choices[0].message.content)


def json_mode():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BASE_URL)
    last_content = None

    for _ in range(3):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": JSON_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Please reply in json. Fill the fields model_name, status, "
                        "greeting, and capabilities. Set model_name to "
                        f"\"{MODEL_NAME}\" and use exactly three short strings "
                        "for capabilities."
                    ),
                },
            ],
        )

        content = response.choices[0].message.content
        last_content = content

        if not content or not content.strip():
            continue

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue

        if is_valid_payload(data):
            print(json.dumps(data, indent=2))
            return

    raise RuntimeError(
        "DeepSeek returned empty or invalid JSON after 3 attempts. "
        f"Last response content: {last_content!r}"
    )


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
