import pytest

from maica.maica_utils.setting_utils import MaicaSettings


def test_verification_properties_are_backed_by_none_private_values() -> None:
    verification = MaicaSettings.Verification()

    assert verification._user_id is None
    assert verification._username is None
    assert verification._nickname is None
    assert verification._email is None
    assert verification.nickname is None
    assert not MaicaSettings.Verification.model_fields
    assert not MaicaSettings.Verification.__annotations__.keys() & {
        "user_id",
        "username",
        "nickname",
        "email",
    }

    for name in ("user_id", "username", "email"):
        with pytest.raises(AssertionError, match=f"{name} must be assigned before access"):
            getattr(verification, name)


def test_verification_properties_validate_and_lock_assignments() -> None:
    verification = MaicaSettings.Verification()

    with pytest.raises(AssertionError):
        verification.user_id = "1"

    verification.user_id = 1
    verification.username = "tester"
    verification.nickname = None
    verification.email = "tester@example.com"

    assert verification.user_id == 1
    assert verification.username == "tester"
    assert verification.nickname is None
    assert verification.email == "tester@example.com"

    with pytest.raises(AssertionError, match="user_id is locked"):
        verification.user_id = 2
