# tests/data/test_chunk.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.
from archive_agent.data.chunk import split_sentences


def test_split_sentences_output():
    with open("./tests/data/test_data/test_unsanitized.txt", "r", encoding="utf-8") as f:
        raw_text = f.read()

    with open("./tests/data/test_data/test_sanitized.txt", "r", encoding="utf-8") as f:
        expected_text = f.read()

    result, _ = split_sentences(raw_text)

    # Join sentences into output form (modern: no "" for paragraph break)
    joined = "\n".join(result)

    # Remove blank lines from both outputs before comparison
    def _strip_blanks(text: str) -> str:
        return "\n".join([line for line in text.splitlines() if line.strip()])

    assert _strip_blanks(joined.strip()) == _strip_blanks(expected_text.strip())


def test_split_sentences_with_ranges():
    raw_text = "This is line one.\nThis is line two.\n\nThis is line three."
    per_line_references = [1, 2, 3, 4]

    result_sentences, result_ranges = split_sentences(raw_text, per_line_references)

    expected_sentences = [
        "This is line one.",
        "This is line two.",
        "This is line three."
    ]
    expected_ranges = [(1, 1), (2, 2), (4, 4)]

    assert result_sentences == expected_sentences
    assert result_ranges == expected_ranges


def test_split_sentences_without_ranges():
    raw_text = "This is line one.\nThis is line two.\n\nThis is line three."

    result_sentences, result_ranges = split_sentences(raw_text)

    expected_sentences = [
        "This is line one.",
        "This is line two.",
        "This is line three."
    ]
    expected_ranges = [(0, 0), (0, 0), (0, 0)]

    assert result_sentences == expected_sentences
    assert result_ranges == expected_ranges
