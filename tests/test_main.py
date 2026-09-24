#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typer.testing import CliRunner

import archive_agent.__main__ as main_module

runner = CliRunner()


def _record_subprocess(monkeypatch):
    calls = []
    monkeypatch.setattr(main_module.subprocess, "run", lambda cmd, **kwargs: calls.append(cmd))
    return calls


def test_gui_refuses_to_start_without_password(monkeypatch):
    monkeypatch.delenv("LOCAL_AUTH_PASSWORD", raising=False)
    calls = _record_subprocess(monkeypatch)

    result = runner.invoke(main_module.app, ["gui"])

    assert result.exit_code != 0
    assert calls == []


def test_gui_binds_ipv4_only(monkeypatch):
    monkeypatch.setenv("LOCAL_AUTH_PASSWORD", "test-pw")
    calls = _record_subprocess(monkeypatch)

    result = runner.invoke(main_module.app, ["gui", "--verbose"])

    assert result.exit_code == 0
    cmd = calls[0]
    assert cmd[cmd.index("--server.address") + 1] == "0.0.0.0"
    assert cmd[-2:] == ["--", "--verbose"]


def test_mcp_refuses_to_start_without_password(monkeypatch):
    monkeypatch.delenv("LOCAL_AUTH_PASSWORD", raising=False)

    def fail_context(*args, **kwargs):
        raise AssertionError("must fail closed before connecting")

    monkeypatch.setattr(main_module, "ContextManager", fail_context)

    result = runner.invoke(main_module.app, ["mcp"])

    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit)
