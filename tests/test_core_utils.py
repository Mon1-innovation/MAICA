import asyncio
import hashlib

from cryptography.hazmat.primitives.asymmetric import rsa

from maica.maica_utils import (
    G,
    MaicaInputWarning,
    MaicaSettings,
    add_seq_suffix,
    crypto_object,
    decrypt_token,
    encrypt_token,
    hash_sha256,
    is_mcore_vl,
    sign_message,
    silent,
    sync_messenger,
    verify_message,
)
from maica.maica_utils.users_utils import FscUsersFuncMixin


def test_hash_sha256_accepts_text() -> None:
    actual = asyncio.run(hash_sha256("角色扮演"))
    expected = hashlib.sha256("角色扮演".encode()).hexdigest()
    assert actual == expected


def test_string_error_codes_are_supported() -> None:
    G.A.DEBUG_WARNS = "0"
    silent(True)
    try:
        packet = sync_messenger(error=MaicaInputWarning("bad input", "400"))
    finally:
        silent(False)
    assert packet[:3] == (400, "maica_unified_warning", "bad input")


def test_empty_model_addresses_do_not_enable_native_vision() -> None:
    G.A.MCORE_ADDR = ""
    G.A.MVISTA_ADDR = ""
    G.A.MCORE_CHOICE = ""
    G.A.MVISTA_CHOICE = ""
    assert is_mcore_vl() is False


def test_none_resets_non_optional_setting_but_preserves_optional_setting() -> None:
    basic = MaicaSettings.Basic.model_validate({"target_lang": None})
    super_settings = MaicaSettings.Super.model_validate({"seed": None})
    assert basic.target_lang == "zh"
    assert super_settings.seed is None


def test_rsa_tokens_and_signatures_round_trip() -> None:
    old_public, old_private = crypto_object.public_key, crypto_object.private_key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    crypto_object.private_key = private_key
    crypto_object.public_key = private_key.public_key()
    try:
        token = encrypt_token('{"username":"tester","password":"secret"}')
        assert decrypt_token(token) == '{"username":"tester","password":"secret"}'

        signature = sign_message("history")
        verify_message("history", signature)
        try:
            verify_message("tampered", signature)
        except ValueError:
            pass
        else:
            raise AssertionError("tampered message passed signature verification")
    finally:
        crypto_object.public_key, crypto_object.private_key = old_public, old_private


def test_credentials_require_exactly_one_identity() -> None:
    for payload in (
        {"password": "secret"},
        {"username": "user", "email": "user@example.com", "password": "secret"},
    ):
        try:
            FscUsersFuncMixin.TokenCridential.model_validate(payload)
        except Exception:
            pass
        else:
            raise AssertionError("ambiguous credentials were accepted")


def test_english_ordinal_suffix_handles_teens() -> None:
    assert [add_seq_suffix(value) for value in (1, 2, 3, 11, 12, 13, 21)] == [
        "1 st", "2 nd", "3 rd", "11 th", "12 th", "13 th", "21 st"
    ]
