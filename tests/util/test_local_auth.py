#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import base64

import pytest

from archive_agent.util.local_auth import ENV_VAR, authorized, get_password, require_password

PASSWORD = "test-pw"


def _basic(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def test_bearer_accepted():
    assert authorized(f"Bearer {PASSWORD}", PASSWORD)


def test_basic_with_any_username_accepted():
    assert authorized(_basic("x", PASSWORD), PASSWORD)
    assert authorized(_basic("", PASSWORD), PASSWORD)


def test_scheme_is_case_insensitive():
    assert authorized(f"bearer {PASSWORD}", PASSWORD)


def test_wrong_or_missing_rejected():
    assert not authorized(None, PASSWORD)
    assert not authorized("", PASSWORD)
    assert not authorized("Bearer wrong", PASSWORD)
    assert not authorized(_basic("x", "wrong"), PASSWORD)
    assert not authorized("Basic not-base64!", PASSWORD)
    assert not authorized(f"Token {PASSWORD}", PASSWORD)


def test_require_password_fails_closed(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(SystemExit):
        require_password()
    monkeypatch.setenv(ENV_VAR, "")
    with pytest.raises(SystemExit):
        require_password()
    assert get_password() is None


def test_require_password_returns_value(monkeypatch):
    monkeypatch.setenv(ENV_VAR, PASSWORD)
    assert require_password() == PASSWORD
