# tests/data/test_chunk.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List

from archive_agent.data.chunk import split_sentences, generate_chunks_with_ranges, SentenceWithRange
from archive_agent.ai.chunk.AiChunk import ChunkSchema


# Golden test (preserved as-is, no refs, structure verification)
def test_split_sentences_output():
    with open("./tests/data/test_data/test_unsanitized.txt", "r", encoding="utf-8") as f:
        raw_text = f.read().strip()

    with open("./tests/data/test_data/test_sanitized.txt", "r", encoding="utf-8") as f:
        expect_text = f.read().strip()

    result = split_sentences(raw_text)

    # Join sentence blocks into output form ("" = paragraph break)
    joined_text = "\n".join([s.text for s in result]).strip()

    print(f"\n{joined_text=}\n")
    print(f"\n{expect_text=}\n")

    assert joined_text == expect_text


# Tests for split_sentences

def test_split_sentences_no_references_simple():
    raw_text = "A.\nB.\n\nC."

    result = split_sentences(raw_text)

    expected = [
        SentenceWithRange("A. B.", (0, 0)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("C.", (0, 0)),
    ]

    assert result == expected


def test_split_sentences_with_references_spanned():
    raw_text = "First. Second spans\nlines.\n\nThird."
    per_line_references = [1, 2, 3, 4]

    result = split_sentences(raw_text, per_line_references)

    expected = [
        SentenceWithRange("First.", (1, 1)),
        SentenceWithRange("Second spans lines.", (1, 2)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("Third.", (4, 4)),
    ]

    assert result == expected


def test_split_sentences_markdown_lists():
    raw_text = "Para.\n\n- Item1.\n- Item2."
    per_line_references = [1, 2, 3, 4]

    result = split_sentences(raw_text, per_line_references)

    expected = [
        SentenceWithRange("Para.", (1, 1)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("- Item1.", (3, 3)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("- Item2.", (4, 4)),
    ]

    assert result == expected


def test_split_sentences_short_references():
    raw_text = "One.\nTwo."
    per_line_references = [1]  # Shorter than lines

    result = split_sentences(raw_text, per_line_references)

    expected = [
        SentenceWithRange("One.", (1, 1)),
        SentenceWithRange("Two.", (0, 0)),
    ]

    assert result == expected


def test_split_sentences_empty_or_blanks():
    # Empty text
    result_empty = split_sentences("")
    assert result_empty == []

    # All blanks
    result_blanks = split_sentences("\n\n")
    assert result_blanks == []


# Tests for generate_chunks_with_ranges (use a dummy chunk_callback returning fixed ChunkSchema; no full AI)

def dummy_chunk_callback(block_of_sentences: List[str]) -> ChunkSchema:
    # Fixed logic: Group all sentences into one chunk (coherent), unless empty
    start_lines = [1] if block_of_sentences else []
    headers = [f"Header 1"] if block_of_sentences else []
    return ChunkSchema(chunk_start_lines=start_lines, headers=headers)


def test_generate_chunks_with_ranges_basic_no_carry():
    sentences_with_ranges = [
        SentenceWithRange("S1", (1, 1)),
        SentenceWithRange("S2", (2, 2)),
    ]
    chunk_lines_block = 2
    file_path = "test.txt"

    result = generate_chunks_with_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path)

    assert len(result) == 1  # One chunk
    assert result[0].reference_range == (1, 2)  # Aggregates valid ranges
    assert "Header 1" in result[0].text  # Format check
    assert "S1\nS2" in result[0].text  # Body content


def test_generate_chunks_with_ranges_with_carry():
    sentences_with_ranges = [
        SentenceWithRange("S1", (1, 1)),
        SentenceWithRange("S2", (2, 2)),
        SentenceWithRange("S3", (3, 3)),
    ]
    chunk_lines_block = 2  # Two blocks: [S1,S2], [S3]
    file_path = "test.txt"

    result = generate_chunks_with_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path)

    assert len(result) == 1  # Adjusted: With dummy grouping, all in one final chunk after carry
    assert result[0].reference_range == (1, 3)  # Aggregates all valid ranges
    assert "Header 1" in result[0].text
    assert "S1\nS2\nS3" in result[0].text


def test_generate_chunks_with_ranges_ignores_zeros_in_agg():
    sentences_with_ranges = [
        SentenceWithRange("S1", (1, 1)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("S2", (2, 2)),
    ]
    chunk_lines_block = 3
    file_path = "test.txt"

    result = generate_chunks_with_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path)

    assert len(result) == 1
    assert result[0].reference_range == (1, 2)  # Ignores (0,0)
    assert "Header 1" in result[0].text
    assert "S1\n\nS2" in result[0].text  # Break preserved


def test_generate_chunks_with_ranges_empty():
    sentences_with_ranges = []
    chunk_lines_block = 1
    file_path = "test.txt"

    result = generate_chunks_with_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path)

    assert result == []
