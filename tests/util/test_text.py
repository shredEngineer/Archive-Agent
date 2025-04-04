#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import pytest

from archive_agent.util.text import ensure_nltk_punkt, is_text, load_as_utf8


def test_ensure_nltk_punkt_does_not_crash():
    try:
        ensure_nltk_punkt()
    except Exception as e:
        pytest.fail(f"ensure_nltk_punkt() raised an exception: {e}")


@pytest.mark.parametrize("filename,expected", [
    ("test.txt", True),
    ("test.md", True),
    ("test.jpg", False),
    ("test.jpeg", False),
])
def test_is_text_recognizes_extensions(filename, expected):
    assert is_text(filename) is expected


def test_load_as_utf8_reads_text(tmp_path):
    test_file = tmp_path / "example.txt"
    test_file.write_text("Hello, world!", encoding="utf-8")
    result = load_as_utf8(str(test_file))
    assert result == "Hello, world!"


def test_load_as_utf8_file_not_found(tmp_path):
    missing_file = tmp_path / "not_there.txt"
    with pytest.raises(typer.Exit) as exc_info:
        load_as_utf8(str(missing_file))
    assert exc_info.value.exit_code == 1
