#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from pathlib import Path
from typing import List, Optional

from archive_agent.standalone.StandaloneOcr import (
    build_markdown,
    get_output_path,
    sanitize_unicode,
)


class TestGetOutputPath:
    """Tests for get_output_path()."""

    def test_replaces_pdf_extension_with_md(self) -> None:
        """Test that .pdf extension is replaced with .md."""
        result = get_output_path("/home/user/document.pdf")
        assert result == Path("/home/user/document.md")

    def test_preserves_directory_path(self) -> None:
        """Test that the directory part of the path is preserved."""
        result = get_output_path("/some/deep/path/report.pdf")
        assert result.parent == Path("/some/deep/path")

    def test_handles_uppercase_pdf_extension(self) -> None:
        """Test that uppercase .PDF extension is replaced."""
        result = get_output_path("/home/user/DOCUMENT.PDF")
        assert result == Path("/home/user/DOCUMENT.md")

    def test_handles_filename_with_dots(self) -> None:
        """Test that only the final extension is replaced."""
        result = get_output_path("/home/user/my.report.v2.pdf")
        assert result == Path("/home/user/my.report.v2.md")


class TestBuildMarkdown:
    """Tests for build_markdown()."""

    def test_empty_input_returns_empty_string(self) -> None:
        """Test that empty page list produces empty string."""
        result = build_markdown([])
        assert result == ""

    def test_single_page_with_text(self) -> None:
        """Test markdown output for a single successful page (no page heading)."""
        result = build_markdown(["Hello world from page one."])
        expected = "Hello world from page one.\n"
        assert result == expected

    def test_multiple_pages(self) -> None:
        """Test markdown output for multiple pages."""
        page_texts: List[Optional[str]] = [
            "Text from page one.",
            "Text from page two.",
            "Text from page three.",
        ]
        result = build_markdown(page_texts)

        assert "Text from page one." in result
        assert "Text from page two." in result
        assert "Text from page three." in result

    def test_no_page_headings(self) -> None:
        """Test that no '# Page N' headings are emitted (structure comes from OCR line breaks)."""
        page_texts: List[Optional[str]] = ["Page one.", "Page two.", "Page three."]
        result = build_markdown(page_texts)
        assert "# Page" not in result

    def test_multiline_text_is_preserved(self) -> None:
        """Test that line breaks within a page are preserved (no collapse to single line)."""
        result = build_markdown(["# Title\n\nA paragraph.\n\n- item one\n- item two"])
        assert "# Title\n\nA paragraph.\n\n- item one\n- item two" in result

    def test_failed_page_shows_unprocessable_marker(self) -> None:
        """Test that None pages produce the unprocessable marker."""
        page_texts: List[Optional[str]] = [
            "Good page.",
            None,
            "Another good page.",
        ]
        result = build_markdown(page_texts)

        assert "*[Unprocessable page]*" in result

    def test_all_pages_failed(self) -> None:
        """Test output when all pages fail."""
        page_texts: List[Optional[str]] = [None, None]
        result = build_markdown(page_texts)

        assert result.count("*[Unprocessable page]*") == 2

    def test_output_ends_with_newline(self) -> None:
        """Test that output ends with a trailing newline."""
        result = build_markdown(["Text."])
        assert result.endswith("\n")

    def test_pages_separated_by_blank_lines(self) -> None:
        """Test that consecutive pages are separated by a blank line."""
        page_texts: List[Optional[str]] = ["Page one.", "Page two."]
        result = build_markdown(page_texts)
        assert "Page one.\n\nPage two." in result

    def test_unicode_spaces_are_sanitized(self) -> None:
        """Test that Unicode whitespace in page text is replaced with regular spaces."""
        page_texts: List[Optional[str]] = ["Hello\u2003world\u00A0foo"]
        result = build_markdown(page_texts)
        assert "Hello world foo" in result
        assert "\u2003" not in result
        assert "\u00A0" not in result


class TestSanitizeUnicode:
    """Tests for sanitize_unicode()."""

    def test_em_space_replaced(self) -> None:
        """Test that em space (U+2003) is replaced with regular space."""
        result = sanitize_unicode("hello\u2003world")
        assert result == "hello world"

    def test_en_space_replaced(self) -> None:
        """Test that en space (U+2002) is replaced with regular space."""
        result = sanitize_unicode("hello\u2002world")
        assert result == "hello world"

    def test_nbsp_replaced(self) -> None:
        """Test that non-breaking space (U+00A0) is replaced with regular space."""
        result = sanitize_unicode("hello\u00A0world")
        assert result == "hello world"

    def test_multiple_unicode_spaces(self) -> None:
        """Test that multiple different Unicode spaces are all replaced."""
        result = sanitize_unicode("a\u2003b\u2009c\u00A0d")
        assert result == "a b c d"

    def test_regular_text_unchanged(self) -> None:
        """Test that regular ASCII text passes through unchanged."""
        text = "Hello world, this is normal text."
        assert sanitize_unicode(text) == text

    def test_preserves_regular_spaces(self) -> None:
        """Test that regular spaces are not doubled or modified."""
        result = sanitize_unicode("hello world")
        assert result == "hello world"

    def test_preserves_non_space_unicode(self) -> None:
        """Test that non-space Unicode characters (math, Greek) are preserved."""
        text = "∂μ θ ∇ × A"
        assert sanitize_unicode(text) == text
