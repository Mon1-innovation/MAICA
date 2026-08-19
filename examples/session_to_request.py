"""Convert a saved MaicaSession into a Responses API request body."""

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

from maica.maica_utils import (
    AiConnectionManager,
    ConnUtils,
    G,
    MaicaSession,
    MaicaSettings,
    get_inner_path,
)
from maica.maica_utils.gvars import pkg_init_gvars


self_path = os.path.dirname(os.path.abspath(__file__))
session_path = os.path.join(self_path, "debug_session.json")
body_path = os.path.join(self_path, "debug_body.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        help=(
            "override the model name; otherwise use MAICA_MCORE_CHOICE, "
            "or the endpoint's first model when it is empty"
        ),
    )
    return parser.parse_args()


def load_settings() -> None:
    # Load project defaults after local overrides, without initializing databases.
    load_dotenv(get_inner_path(".env"))
    load_dotenv(get_inner_path("env_basis"))
    pkg_init_gvars()


def load_session() -> MaicaSession:
    with open(session_path, encoding="utf-8") as f:
        saved_session = json.load(f)

    session = MaicaSession()
    session.load(saved_session)
    return session


async def create_connection(model_override: str | None) -> AiConnectionManager:
    if not model_override:
        # This is the same initialization path used by the running project. It
        # resolves the endpoint's first model when MCORE_CHOICE is empty.
        return await ConnUtils.mcore_conn()

    connection = AiConnectionManager(
        api_key=G.A.MCORE_KEY,
        base_url=G.A.MCORE_ADDR,
        name="mcore_conn",
        model=model_override,
    )
    connection.model_actual = model_override
    connection.default_params(**json.loads(G.A.MCORE_EXTRA))
    return connection


def build_responses_request_body(
    session: MaicaSession,
    connection: AiConnectionManager,
) -> dict:
    settings = MaicaSettings()
    completion_args = {
        "input": session.utilize(),
        "stream": settings.use_stream_now,
        "extra_body": {},
    }
    completion_args.update(settings.super.model_dump())

    target_lang = session[-1].target_lang or settings.basic.target_lang
    if settings.extra.gen_enforce_lang and target_lang == "en":
        completion_args["extra_body"]["structured_outputs"] = {
            "regex": r"^[^\u4e00-\u9fa5]*$"
        }

    return connection.completions_to_request_body(**completion_args)


async def async_main(model_override: str | None) -> None:
    load_settings()
    session = load_session()
    connection = await create_connection(model_override)

    try:
        request_body = build_responses_request_body(session, connection)
        if reconfigure := getattr(sys.stdout, "reconfigure", None):
            reconfigure(encoding="utf-8")

        with open(body_path, 'x', encoding='utf-8') as f:
            f.write(json.dumps(request_body, ensure_ascii=False, indent=2))
    finally:
        await connection.close()


def main() -> None:
    args = parse_args()
    asyncio.run(async_main(args.model))


if __name__ == "__main__":
    main()
