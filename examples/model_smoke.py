"""Manual smoke test for an OpenAI-compatible model endpoint.

This script intentionally isn't part of the automated test suite because it
requires a configured, running model deployment.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()
    client = OpenAI(
        base_url=os.environ["MAICA_MCORE_ADDR"],
        api_key=os.getenv("MAICA_MCORE_KEY") or "-",
    )
    model = client.models.list().data[0].id
    response = client.responses.create(model=model, input="你好")
    print(response.output_text)


if __name__ == "__main__":
    main()
