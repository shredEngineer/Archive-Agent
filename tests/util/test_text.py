#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import pytest

from archive_agent.util.text import is_text, load_text


def test_pandoc_is_installed():
    import pypandoc
    try:
        version = pypandoc.get_pandoc_version()
        assert version is not None
    except OSError as e:
        pytest.fail(f"Pandoc is not installed or not in PATH: {e}")


@pytest.mark.parametrize("file_path,expected", [
    ("test.txt", True),
    ("test.md", True),
    ("test.odt", True),
    ("test.docx", True),
    ("test.rtf", True),
    ("test.html", True),
    ("test.jpg", False),
    ("test.jpeg", False),
])
def test_is_text_recognizes_extensions(file_path, expected):
    assert is_text(file_path) is expected


def test_load_plaintext_reads_text(tmp_path):
    test_file = tmp_path / "example.txt"
    test_file.write_text("Hello, world!", encoding="utf-8")
    result = load_text(str(test_file))
    assert result == "Hello, world!"


def test_load_text_file_not_found(tmp_path):
    missing_file = tmp_path / "not_there.txt"
    with pytest.raises(typer.Exit) as exc_info:
        load_text(str(missing_file))
    assert exc_info.value.exit_code == 1
