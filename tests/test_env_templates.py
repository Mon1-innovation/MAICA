import json
import os
import sys
from io import StringIO
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values

from maica import maica_starter


@pytest.fixture
def env_setup(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(maica_starter, "initialized", False)
    monkeypatch.setattr(maica_starter, "start_target", "chat")
    monkeypatch.setattr(maica_starter, "validate_only", False)
    monkeypatch.setattr(maica_starter, "_silent", lambda _silent: None)
    monkeypatch.setattr(os, "environ", {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MAICA_", "MTTS_"))
    })
    mtts_basis = tmp_path / "mtts_env_basis"
    mtts_basis.write_text(
        "# MTTS version metadata\n"
        "MTTS_CURR_VERSION = '9.9.9'\n"
        "MTTS_LEGC_VERSION = '9.0.0'\n"
        "MTTS_SYNBRACE_CAPV = '9.0.0'\n"
        "\n"
        "# MTTS settings\n"
        "MTTS_TTS_ADDR = 'http://tts.invalid/tts'\n"
        "MTTS_HTTP_PORT = '7100'\n"
        "MTTS_FUTURE_SETTING = 'from-installed-mtts'\n"
        "MTTS_TTS_EXTRA = '\n{\n    \"future_option\": true\n}\n'",
        encoding="utf-8",
    )
    monkeypatch.setattr(maica_starter, "mtts_installed", True)
    monkeypatch.setattr(
        maica_starter,
        "mtts_locater",
        SimpleNamespace(get_inner_path=lambda filename: str(tmp_path / filename)),
        raising=False,
    )
    return tmp_path


@pytest.mark.parametrize("mtts_installed", [False, True])
@pytest.mark.parametrize("operation", ["print", "create"])
def test_templates_include_installed_package_settings(
    env_setup, monkeypatch, capsys, mtts_installed, operation
) -> None:
    monkeypatch.setattr(maica_starter, "mtts_installed", mtts_installed)
    monkeypatch.setattr(sys, "argv", ["maica", "-t", operation])

    with pytest.raises(SystemExit) as exc_info:
        maica_starter.check_params()
    assert exc_info.value.code is None

    if operation == "create":
        template = (env_setup / ".env").read_text(encoding="utf-8")
    else:
        template = "\n".join(capsys.readouterr().out.splitlines()[1:-1])
    values = dotenv_values(stream=StringIO(template))

    assert values["MAICA_IS_REAL_ENV"] == "0"
    assert "#MAICA_PROMPT_ZC = " in template
    assert not any(key.startswith("MAICA_PROMPT_") for key in values)
    for key in (
        "MAICA_CURR_VERSION", "MAICA_LEGC_VERSION", "MAICA_BLESSLAND_CAPV",
        "MTTS_CURR_VERSION", "MTTS_LEGC_VERSION", "MTTS_SYNBRACE_CAPV",
    ):
        assert key not in values

    if mtts_installed:
        assert values["MTTS_TTS_ADDR"] == "http://tts.invalid/tts"
        assert values["MTTS_HTTP_PORT"] == "7100"
        assert values["MTTS_FUTURE_SETTING"] == "from-installed-mtts"
        assert json.loads(values["MTTS_TTS_EXTRA"]) == {"future_option": True}
        assert template.count("MTTS_TTS_ADDR =") == 1
    else:
        assert not any(key.startswith("MTTS_") for key in values)


@pytest.mark.parametrize("mtts_installed", [False, True])
def test_runtime_loads_defaults_from_installed_packages(
    env_setup, monkeypatch, mtts_installed
) -> None:
    monkeypatch.setattr(maica_starter, "mtts_installed", mtts_installed)
    maica_starter.check_params(envdir=str(env_setup / ".env"), parse_cli=False)

    assert os.environ["MAICA_WS_PORT"] == "5000"
    assert os.environ["MAICA_CURR_VERSION"]
    if mtts_installed:
        assert os.environ["MTTS_CURR_VERSION"] == "9.9.9"
        assert os.environ["MTTS_HTTP_PORT"] == "7100"
        assert os.environ["MTTS_FUTURE_SETTING"] == "from-installed-mtts"
    else:
        assert not any(key.startswith("MTTS_") for key in os.environ)


def test_user_settings_take_precedence_over_package_defaults(env_setup, monkeypatch) -> None:
    env_file = env_setup / ".env"
    env_file.write_text(
        "MAICA_WS_PORT = '5100'\nMTTS_HTTP_PORT = '7200'\n"
        "MTTS_TTS_ADDR = 'http://env.invalid/tts'\n",
        encoding="utf-8",
    )
    extra_file = env_setup / "extra.env"
    extra_file.write_text(
        "MAICA_WS_PORT = '5200'\nMTTS_HTTP_PORT = '7300'\n"
        "MTTS_FUTURE_SETTING = 'extra-override'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MTTS_HTTP_PORT", "7400")

    maica_starter.check_params(
        envdir=str(env_file),
        extra_envdir=[str(extra_file)],
        parse_cli=False,
        MTTS_TTS_ADDR="http://kwargs.invalid/tts",
    )

    assert os.environ["MAICA_WS_PORT"] == "5100"
    assert os.environ["MTTS_HTTP_PORT"] == "7400"
    assert os.environ["MTTS_TTS_ADDR"] == "http://kwargs.invalid/tts"
    assert os.environ["MTTS_FUTURE_SETTING"] == "extra-override"
