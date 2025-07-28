# tests/data/test_chunk.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.data.chunk import get_sentences_with_reference_ranges, get_chunks_with_reference_ranges, SentenceWithRange
from archive_agent.ai.chunk.AiChunk import ChunkSchema, ChunkItem
from archive_agent.util.text_util import splitlines_exact

logger = logging.getLogger(__name__)


def test_split_sentences_output():
    """
    Verify that `split_sentences` preserves text structure for a real file without references.
    Loads a test file (`test_unsanitized.txt`) and checks its joined sentences match a sanitized version (`test_sanitized.txt`).
    Tests: Structure preservation (paragraph breaks as ""), no-reference case with (0,0) ranges.
    """
    with open("./tests/data/test_data/test_unsanitized.txt", "r", encoding="utf-8") as f:
        raw_text = f.read().strip()

    with open("./tests/data/test_data/test_sanitized.txt", "r", encoding="utf-8") as f:
        expect_text = f.read().strip()

    doc_content = DocumentContent(text=raw_text, lines_per_line=list(range(len(splitlines_exact(raw_text)))))
    result = get_sentences_with_reference_ranges(doc_content)

    joined_text = "\n".join([s.text for s in result]).strip()

    print(f"\n{joined_text=}\n")
    print(f"\n{expect_text=}\n")

    assert joined_text == expect_text


def test_split_sentences_simple():
    """
    Test `split_sentences` with a simple text.
    Input: Text with two sentences in one paragraph, a break, and a third sentence.
    Expected: Sentences joined in first paragraph, break as "", third sentence separate.
    Tests: Paragraph breaks, sentence joining by spaCy.
    """
    raw_text = "A.\nB.\n\nC."

    doc_content = DocumentContent(
        text=raw_text,
        lines_per_line=[1, 2, 3, 4],
    )
    result = get_sentences_with_reference_ranges(doc_content)

    expected = [
        SentenceWithRange("A. B.", (1, 2)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("C.", (4, 4)),
    ]

    assert result == expected


def test_split_sentences_with_references_spanned():
    """
    Test `split_sentences` with references and a sentence spanning multiple lines.
    Input: Text with a single-line sentence, a multi-line sentence, a break, and another sentence; references [1,2,3,4].
    Expected: Sentences with min-max ranges (e.g., (1,2) for spanned), break as "" (0,0).
    Tests: Reference aggregation, multi-line sentences, monotonic references.
    """
    doc_content = DocumentContent(
        text="First. Second spans\nlines.\n\nThird.",
        lines_per_line=[1, 2, 3, 4],
    )

    result = get_sentences_with_reference_ranges(doc_content)

    expected = [
        SentenceWithRange("First.", (1, 1)),
        SentenceWithRange("Second spans lines.", (1, 2)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("Third.", (4, 4)),
    ]

    assert result == expected


def test_split_sentences_markdown_lists():
    """
    Test `split_sentences` with Markdown list items as separate paragraphs.
    Input: Text with a paragraph, break, and two list items; references [1,2,3,4].
    Expected: Paragraph, break, each list item as separate sentence, breaks between, with correct ranges.
    Tests: Markdown list handling, paragraph breaks, reference assignment.
    """
    doc_content = DocumentContent(
        text="Para.\n\n- Item1.\n- Item2.",
        lines_per_line=[1, 2, 3, 4],
    )

    result = get_sentences_with_reference_ranges(doc_content)

    expected = [
        SentenceWithRange("Para.", (1, 1)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("- Item1.", (3, 3)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("- Item2.", (4, 4)),
    ]

    assert result == expected


def test_split_sentences_empty_or_blanks():
    """
    Test `split_sentences` with empty or blank-only input.
    Input: Empty string or multiple blank lines.
    Expected: Empty list for both cases.
    Tests: Edge cases for empty input, blank line handling.
    """
    doc_content = DocumentContent(
        text="",
        lines_per_line=[1],
    )

    result_empty = get_sentences_with_reference_ranges(doc_content)
    assert result_empty == []

    doc_content = DocumentContent(
        text="\n\n",
        lines_per_line=[1, 2, 3],
    )

    result_blanks = get_sentences_with_reference_ranges(doc_content)
    assert result_blanks == []


def dummy_chunk_callback(block_of_sentences: List[str]) -> ChunkSchema:
    """
    Simulate AI chunking with a fixed, single-chunk output.
    Input: List of sentences.
    Output: ChunkSchema with one chunk starting at line 1, with a header, or empty if no sentences.
    Used to test chunking logic deterministically.
    """
    return ChunkSchema(chunk_items=[ChunkItem(start_line=1, header="Header 1")] if block_of_sentences else [])


def test_generate_chunks_with_ranges_basic_no_carry():
    """
    Test `generate_chunks_with_ranges` with a small block, no carry-over.
    Input: Two sentences with ranges (1,1), (2,2); block size 2.
    Expected: One chunk with all sentences, aggregated range (1,2), formatted with header.
    Tests: Basic chunking, range aggregation, formatting.
    """
    sentences_with_ranges = [
        SentenceWithRange("S1", (1, 1)),
        SentenceWithRange("S2", (2, 2)),
    ]
    chunk_lines_block = 2
    file_path = "test.txt"

    result = get_chunks_with_reference_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path, logger)

    assert len(result) == 1
    assert result[0].reference_range == (1, 2)
    assert "Header 1" in result[0].text
    assert "S1\nS2" in result[0].text


def test_generate_chunks_with_ranges_with_carry():
    """
    Test `generate_chunks_with_ranges` with multiple blocks and carry-over.
    Input: Three sentences with ranges (1,1), (2,2), (3,3); block size 2.
    Expected: One chunk grouping all sentences (due to dummy callback), range (1,3).
    Tests: Block grouping, carry-over handling, range aggregation.
    """
    sentences_with_ranges = [
        SentenceWithRange("S1", (1, 1)),
        SentenceWithRange("S2", (2, 2)),
        SentenceWithRange("S3", (3, 3)),
    ]
    chunk_lines_block = 2
    file_path = "test.txt"

    result = get_chunks_with_reference_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path, logger)

    assert len(result) == 1
    assert result[0].reference_range == (1, 3)
    assert "Header 1" in result[0].text
    assert "S1\nS2\nS3" in result[0].text


def test_generate_chunks_with_ranges_ignores_zeros_in_agg():
    """
    Test `generate_chunks_with_ranges` with a break (0,0) in sentences.
    Input: Two sentences with (1,1), (2,2), a break (0,0); block size 3.
    Expected: One chunk with sentences, range (1,2) ignoring (0,0), break preserved.
    Tests: Sentinel (0,0) filtering, paragraph break preservation.
    """
    sentences_with_ranges = [
        SentenceWithRange("S1", (1, 1)),
        SentenceWithRange("", (0, 0)),
        SentenceWithRange("S2", (2, 2)),
    ]
    chunk_lines_block = 3
    file_path = "test.txt"

    result = get_chunks_with_reference_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path, logger)

    assert len(result) == 1
    assert result[0].reference_range == (1, 2)
    assert "Header 1" in result[0].text
    assert "S1\n\nS2" in result[0].text


def test_generate_chunks_with_ranges_empty():
    """
    Test `generate_chunks_with_ranges` with empty input.
    Input: Empty list of sentences; block size 1.
    Expected: Empty list of chunks.
    Tests: Edge case for empty input handling.
    """
    sentences_with_ranges = []
    chunk_lines_block = 1
    file_path = "test.txt"

    result = get_chunks_with_reference_ranges(sentences_with_ranges, dummy_chunk_callback, chunk_lines_block, file_path, logger)

    assert result == []
