#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from streamlit.proto.TextInput_pb2 import TextInput
from streamlit.testing.v1 import AppTest

# TODO: Test the rest of the GUI


def _gated_app():
    import streamlit as st
    from archive_agent.core.GuiManager import GuiManager

    GuiManager.require_login()
    st.markdown("inside")


def _run(monkeypatch, password):
    if password is None:
        monkeypatch.delenv("LOCAL_AUTH_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("LOCAL_AUTH_PASSWORD", password)
    at = AppTest.from_function(_gated_app, default_timeout=30)
    at.run()
    return at


def _rendered(at):
    return [m.value for m in at.markdown]


def test_gate_fails_closed_without_password(monkeypatch):
    at = _run(monkeypatch, None)
    assert "inside" not in _rendered(at)
    assert len(at.text_input) == 0
    assert "LOCAL_AUTH_PASSWORD is not set" in at.error[0].value


def test_gate_blocks_until_login(monkeypatch):
    at = _run(monkeypatch, "test-pw")
    assert "inside" not in _rendered(at)
    assert at.text_input[0].proto.type == TextInput.Type.PASSWORD


def test_gate_rejects_wrong_password(monkeypatch):
    at = _run(monkeypatch, "test-pw")
    at.text_input[0].input("wrong")
    at.button[0].click().run()
    assert "inside" not in _rendered(at)
    assert at.error[0].value == "Wrong password."
    assert "authenticated" not in at.session_state


def test_gate_opens_on_correct_password_and_stays_open(monkeypatch):
    at = _run(monkeypatch, "test-pw")
    at.text_input[0].input("test-pw")
    at.button[0].click().run()
    assert "inside" in _rendered(at)
    assert len(at.text_input) == 0
    at.run()
    assert "inside" in _rendered(at)
