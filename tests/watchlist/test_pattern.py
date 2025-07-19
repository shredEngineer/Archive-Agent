#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import os
import pytest
import typer

from archive_agent.watchlist.pattern import resolve_pattern, validate_pattern


def test_resolve_pattern_returns_absolute_paths(tmp_path):
    test_file = tmp_path / "example.txt"
    test_file.write_text("hello")

    pattern = str(tmp_path / "*.txt")
    resolved = resolve_pattern(pattern)

    assert len(resolved) == 1
    assert resolved[0] == os.path.abspath(test_file)


def test_resolve_pattern_filters_out_dirs(tmp_path):
    (tmp_path / "some_dir").mkdir()
    (tmp_path / "some_file.txt").write_text("file")

    pattern = str(tmp_path / "*")
    resolved = resolve_pattern(pattern)

    assert all(os.path.isfile(p) for p in resolved)
    assert any("some_file.txt" in p for p in resolved)
    assert all("some_dir" not in p for p in resolved)


def test_resolve_pattern_returns_empty_if_no_match(tmp_path):
    pattern = str(tmp_path / "*.nomatch")
    resolved = resolve_pattern(pattern)
    assert resolved == []


def test_resolve_pattern_returns_sorted(tmp_path):
    (tmp_path / "b.txt").write_text("1")
    (tmp_path / "a.txt").write_text("2")

    pattern = str(tmp_path / "*.txt")
    resolved = resolve_pattern(pattern)

    assert resolved == sorted(resolved)


def test_validate_pattern_expands_home(monkeypatch):
    fake_home = "/fake/home"
    monkeypatch.setenv("HOME", fake_home)

    input_pattern = "~/data/*.txt"
    result = validate_pattern(input_pattern)
    assert result.startswith(fake_home)


def test_validate_pattern_accepts_absolute(tmp_path):
    pattern = str(tmp_path / "*.txt")
    result = validate_pattern(pattern)
    assert result == pattern


def test_validate_pattern_rejects_relative():
    with pytest.raises(typer.Exit) as exc_info:
        validate_pattern("relative/path/*.txt")
    assert exc_info.value.exit_code == 1
