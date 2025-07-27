# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

"""
    ## Overview of Text Processing and Chunking

    This module turns raw document text into searchable chunks for Archive Agent.
    It extends the README's sections on "smart chunking" and "chunk references."
    The focus is on making chunks meaningful and traceable.
    It handles both line-based and page-based files in the same way.

    ### Key Concepts for Beginners

    - **Text Input**: Starts with plain text from files like `.txt` or `.pdf`.
      Optional list of numbers—one per line—for line numbers or page numbers.

    - **Processing Steps**: Cleans text by removing extra spaces.
      Groups into paragraphs.
      Splits into sentences using `spaCy` with custom Markdown handling.
      Chunks with AI help.

    - **Tracing Back**: Each chunk gets a range like `(2,4)` for pages 2 to 4.
      Ranges are approximate due to joining and splitting content.

    - **Special Marker `(0,0)`**: Placeholder for items without a real reference, like paragraph breaks.
      Ignored later to avoid fake "page 0".

    ### Specs: What the Module Must Do

    - **Agnostic Handling**: Treat line numbers and page numbers the same—no special cases.
      Default to `(0,0)` if no numbers are given.

    - **Structure Preservation**: Keep paragraph breaks using empty strings `""`.
      Respect Markdown lists and headings as separate paragraphs.

    - **Sentence Splitting**: Join paragraph lines with spaces.
      Use `spaCy` to break into sentences.

    - **Range Approximation**: For sentences spanning lines, aggregate to min-max.
      For example, lines 1 to 3 become `(1,3)`.
      Ignore `(0,0)` in final chunks.

    - **Chunking**: Group sentences into blocks.
      Call AI for splits and headers.
      Handle leftovers with carry-over across blocks.

    - **Output**: Paired dataclasses for text and range.
      From splitting: `List[SentenceWithRange]`.
      From chunking: `List[ChunkWithRange]`.

    - **Robustness**: Handle short or missing references by defaulting to 0.
      Return empty list `[]` for empty input.
      Skip blanks.

    ### Implementation Details for Developers

    - **Function `get_sentences_with_reference_ranges`**: Main entry point.
      Strips lines.
      Builds paragraph blocks in `_extract_paragraphs_with_reference_ranges` (handles blanks, Markdown lists and headings).
      Normalizes whitespace in `_normalize_inline_whitespace`.
      Sentencizes in `_extract_paragraph_sentences_with_reference_ranges` (uses bisect for reference aggregation).
      Inserts `"" (0,0)` for breaks.
      Returns `List[SentenceWithRange]`.

    - **Function `get_chunks_with_reference_ranges`**: Takes sentences.
      Groups blocks.
      Calls callback for `ChunkSchema` (starts and headers).
      Extracts chunks and carry.
      Aggregates ranges in `_aggregate_ranges` (filters >0).
      Formats in `_format_chunk`.
      Returns `List[ChunkWithRange]`.

    - **Sentinel `(0,0)` Handling**: Inserted for breaks or no references.
      Filtered in aggregation to keep traces clean.
      No inheritance to maintain honest mapping.

    - **Edge Cases**: Short references default to 0.
      Monotonic references preserved in min-max.
      `spaCy` model `en_core_web_md` for sentence splitting,
      with custom component `_spacy_markdown_sentence_fixer` for better Markdown handling.

    - **Types**: `ReferenceList=List[int]`.
      `SentenceRange=Tuple[int, int]`.
      Dataclasses avoid parallel lists.

    For tests, see `test_chunk.py`.
    For integration, see `FileData.py`.
"""

from logging import Logger
import re
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass

import spacy
from spacy import Language  # type: ignore
from spacy.language import Language
from spacy.tokens import Doc
import bisect

from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.util.format import format_file
from archive_agent.util.text_util import splitlines_exact


ReferenceList = List[int]
SentenceRange = Tuple[int, int]


@dataclass
class SentenceWithRange:
    text: str
    reference_range: SentenceRange


@dataclass
class ChunkWithRange:
    text: str
    reference_range: SentenceRange


def _normalize_inline_whitespace(text: str) -> str:
    """
    Normalize inline whitespace inside a string:
    - Replace tabs and non-breaking spaces with normal space
    - Collapse multiple spaces into one
    - Strip leading and trailing whitespace

    :param text: Single paragraph string
    :return: Cleaned inline text
    """
    text = text.replace("\t", " ").replace("\xa0", " ")
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _extract_paragraph_sentences_with_reference_ranges(
    paragraph_lines: List[str],
    paragraph_reference_ranges: ReferenceList,
    nlp: Language
) -> List[SentenceWithRange]:
    """
    Process a single paragraph block: Normalize, sentencize, and compute ranges.

    :param paragraph_lines: Lines in the paragraph.
    :param paragraph_reference_ranges: Associated line references.
    :param nlp: spaCy NLP pipeline.
    :return: List of SentenceWithRange for the block.
    """
    normalized_lines = [_normalize_inline_whitespace(line) for line in paragraph_lines]
    para_text = " ".join(normalized_lines)

    line_starts: Optional[List[int]] = None
    if paragraph_reference_ranges:
        line_starts = [0]
        for norm_line in normalized_lines[:-1]:
            line_starts.append(line_starts[-1] + len(norm_line) + 1)

    doc = nlp(para_text)

    block_sentences: List[SentenceWithRange] = []

    for sentence in doc.sents:
        sentence_text = sentence.text.strip()

        if sentence_text and paragraph_reference_ranges and line_starts:
            start_char = sentence.start_char
            end_char = sentence.end_char

            start_line_idx = bisect.bisect_right(line_starts, start_char) - 1
            start_line_idx = min(start_line_idx, len(paragraph_lines) - 1)

            end_line_idx = bisect.bisect_right(line_starts, end_char - 1) - 1
            end_line_idx = min(end_line_idx, len(paragraph_lines) - 1)

            sentence_refs = paragraph_reference_ranges[start_line_idx: end_line_idx + 1]
            min_ref = min(sentence_refs) if sentence_refs else 0
            max_ref = max(sentence_refs) if sentence_refs else 0
        else:
            min_ref = max_ref = 0

        block_sentences.append(SentenceWithRange(sentence_text, (min_ref, max_ref)))

    return block_sentences


@Language.component("_spacy_markdown_sentence_fixer")
def _spacy_markdown_sentence_fixer(doc: Doc) -> Doc:
    """
    Adjust sentence segmentation to better handle Markdown syntax.
    Prevents sentence breaks after Markdown-specific tokens like headers, list items, and code blocks.
    """
    skip_next = False
    for i, token in enumerate(doc[:-1]):
        if skip_next:
            doc[i + 1].is_sent_start = False
            skip_next = False
            continue

        # Inline code or triple backticks
        if token.text in {"`", "```"}:
            doc[i + 1].is_sent_start = False
            continue

        # Markdown headers
        if token.text.startswith("#"):
            doc[i + 1].is_sent_start = False
            continue

        # Bullet list
        if token.text in {"-", "*"} and (i == 0 or doc[i - 1].text == "\n"):
            doc[i + 1].is_sent_start = False
            continue

        # Avoid break inside code block fences
        if token.text == "```":
            skip_next = True

    return doc


def _get_nlp() -> Language:
    """
    Get NLP model for sentence splitting.
    :return: spaCy language model.
    """
    nlp = spacy.load("en_core_web_md", disable=["parser"])

    nlp.max_length = 100_000_000

    if not nlp.has_pipe("sentencizer"):
        nlp.add_pipe("sentencizer")

    if not nlp.has_pipe("_spacy_markdown_sentence_fixer"):
        nlp.add_pipe("_spacy_markdown_sentence_fixer", after="sentencizer")

    return nlp


def text_to_clean_lines(text: str) -> List[str]:
    lines = splitlines_exact(text)
    stripped_lines = [line.strip() for line in lines]
    return stripped_lines


# TODO: Refactor to use nested DocumentContent instead of bare type
ParagraphWithReferenceRanges = Tuple[List[str], ReferenceList]

def _extract_paragraphs_with_reference_ranges(
        lines: List[str],
        per_line_references: ReferenceList,
) -> List[ParagraphWithReferenceRanges]:
    """
    Extract paragraphs from text lines.
    - Respects empty lines.
    - Turns Markdown list items into separate paragraphs to let NLP (spaCy) work properly.
    - Turns Markdown headings into separate paragraphs.
    :param lines: Text lines.
    :param per_line_references: Per-line reference numbers (lines or pages).
    :return: List of (paragraph lines, associated refs) tuples.
    """
    para_blocks: List[ParagraphWithReferenceRanges] = []

    current_paragraph: List[str] = []
    current_references: ReferenceList = []

    has_references = bool(per_line_references)

    for line_index, line_text in enumerate(lines):

        next_paragraph = False
        discard_line = False

        # Empty line starts new paragraph
        if not line_text:
            next_paragraph = True
            discard_line = True

        # Markdown item starts new paragraph
        if line_text.startswith("- "):
            next_paragraph = True

        # Markdown heading starts new paragraph
        if line_text.startswith("#"):
            next_paragraph = True

        # Push current paragraph and start next
        if next_paragraph:
            if current_paragraph:
                para_blocks.append((current_paragraph, current_references))
                current_paragraph = []
                current_references = []

        # Discard line
        if discard_line:
            continue

        # Append text line with page or line number reference
        current_paragraph.append(line_text)
        if has_references:
            current_references.append(per_line_references[line_index])

        # If heading, push as single-line paragraph
        if line_text.startswith("#"):
            para_blocks.append((current_paragraph, current_references))
            current_paragraph = []
            current_references = []

    # Push last paragraph if non-empty
    if current_paragraph:
        para_blocks.append((current_paragraph, current_references))

    return para_blocks


def _extract_sentences_with_reference_ranges(
        paragraphs_with_reference_ranges: List[ParagraphWithReferenceRanges],
        nlp: Language,
) -> List[SentenceWithRange]:
    sentences_with_reference_ranges: List[SentenceWithRange] = []

    for paragraph_index, (paragraph_lines, paragraph_reference_ranges) in enumerate(paragraphs_with_reference_ranges):

        if paragraph_index > 0:
            # Insert paragraph delimiter: empty sentence with zero range.
            # (Unit tests are sentitive to this logic)
            sentences_with_reference_ranges.append(SentenceWithRange("", (0, 0)))

        paragraph_sentences_with_reference_ranges = _extract_paragraph_sentences_with_reference_ranges(
            paragraph_lines=paragraph_lines,
            paragraph_reference_ranges=paragraph_reference_ranges,
            nlp=nlp,
        )

        sentences_with_reference_ranges.extend(paragraph_sentences_with_reference_ranges)

    return sentences_with_reference_ranges


# noinspection PyDefaultArgument
def get_sentences_with_reference_ranges(text: str, per_line_references: ReferenceList = []) -> List[SentenceWithRange]:
    """
    Use preprocessing and NLP (spaCy) to split text into sentences, keeping track of references.

    Processes text with paragraph and sentence handling, inferring ranges from provided references (lines or pages)
    if available, or defaulting to (0, 0).

    :param text: Input text (arbitrary, may have blank lines).
    :param per_line_references: Per-line reference numbers (e.g., absolute line or page numbers).
    :return: List of SentenceWithRange (text and range pairs).
    """
    clean_lines = text_to_clean_lines(text)

    paragraphs_with_reference_ranges = _extract_paragraphs_with_reference_ranges(clean_lines, per_line_references)

    return _extract_sentences_with_reference_ranges(
        paragraphs_with_reference_ranges=paragraphs_with_reference_ranges,
        nlp=_get_nlp(),
    )


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


def _group_blocks_of_sentences(sentences: List[str], sentences_per_block: int) -> List[List[str]]:
    """
    Group sentences into blocks of a specified size.

    :param sentences: List of all sentences.
    :param sentences_per_block: Number of sentences per block.
    :return: List of sentence blocks.
    """
    return [sentences[i:i + sentences_per_block] for i in range(0, len(sentences), sentences_per_block)]


def _chunk_start_to_ranges(start_lines: List[int], total_lines: int) -> List[SentenceRange]:
    """
    Convert a list of chunk start lines into ranges of sentence indices.

    :param start_lines: List of starting line numbers for chunks.
    :param total_lines: Total number of lines in the block.
    :return: List of (start, end) ranges for each chunk.
    """
    extended = start_lines + [total_lines + 1]
    return list(zip(extended[:-1], extended[1:]))


def _extract_chunks_and_carry(sentences: List[str], ranges: List[SentenceRange]) -> Tuple[List[str], str | None]:
    """
    Extract chunks and any carry-over text from sentences based on ranges.

    :param sentences: List of sentences in the block.
    :param ranges: List of (start, end) ranges for chunks.
    :return: Tuple of (list of chunk texts, carry-over text or None).
    """
    if not ranges:
        return [], None

    if len(ranges) == 1:
        start, end = ranges[0]
        return [], "\n".join(sentences[start - 1:end - 1])

    *main, last = ranges
    chunks = ["\n".join(sentences[start - 1:end - 1]) for start, end in main]
    carry = "\n".join(sentences[last[0] - 1:last[1] - 1])
    return chunks, carry


def _aggregate_ranges(reference_ranges: List[SentenceRange]) -> SentenceRange:
    """
    Aggregate min and max references from a list of ranges, ignoring zeros.

    :param reference_ranges: List of (min, max) reference ranges.
    :return: Aggregated (min, max) reference.
    """
    valid_mins = [min_r for min_r, _ in reference_ranges if min_r > 0]
    valid_maxs = [max_r for _, max_r in reference_ranges if max_r > 0]
    r_min = min(valid_mins) if valid_mins else 0
    r_max = max(valid_maxs) if valid_maxs else 0
    return r_min, r_max


def _format_chunk(file_path: str, header: str, body: str) -> str:
    """
    Format chunk.

    :param file_path: File path.
    :param header: Chunk header.
    :param body: Chunk body.
    :return: Formatted chunk text.
    """
    return "\n".join([
        f"# {format_file(file_path)}",
        f"# {header}",
        f"",
        body,
    ])


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


def get_chunks_with_reference_ranges(
    sentences_with_references: List[SentenceWithRange],
    chunk_callback: Callable[[List[str]], ChunkSchema],
    chunk_lines_block: int,
    file_path: str,
    logger: Logger,
    verbose: bool = True,
) -> List[ChunkWithRange]:
    """
    Chunkify a list of sentences into AI-determined chunks, carrying over leftover sentences where needed,
    and annotate each chunk with the corresponding (min, max) line reference range.

    :param sentences_with_references: List of sentences with their reference ranges.
    :param chunk_callback: Chunk callback.
    :param chunk_lines_block: Number of sentences per block to be chunked.
    :param file_path: Path to the originating file (used for logging and labeling).
    :param logger: Logger.
    :param verbose: Enable to show additional information.
    :return: List of ChunkWithRange objects containing the formatted chunk and its reference range.
    """
    sentences = [s.text for s in sentences_with_references]
    sentence_reference_ranges = [s.reference_range for s in sentences_with_references]

    if len(sentence_reference_ranges) != len(sentences):
        raise ValueError(
            f"Reference range mismatch: "
            f"{len(sentence_reference_ranges)} ranges, "
            f"{len(sentences)} sentences "
            f"for {format_file(file_path)}"
        )

    blocks_of_sentences = _group_blocks_of_sentences(sentences, chunk_lines_block)

    chunks_with_ranges: List[ChunkWithRange] = []
    carry: Optional[str] = None
    carry_reference_ranges: Optional[List[SentenceRange]] = None
    last_carry_header: Optional[str] = None

    idx = 0
    for block_index, block_of_sentences in enumerate(blocks_of_sentences):
        block_len = len(block_of_sentences)
        block_sentence_reference_ranges = sentence_reference_ranges[idx: idx + block_len]
        idx += block_len

        logger.info(f"Chunking block ({block_index + 1}) / ({len(blocks_of_sentences)}) of {format_file(file_path)}")

        if carry:
            assert carry_reference_ranges is not None
            carry_lines = splitlines_exact(carry)

            current_block_line_count: int = len(carry_lines) + len(block_of_sentences)

            if verbose:
                logger.info(f"Carrying over ({len(carry_lines)}) lines; current block has ({current_block_line_count}) lines")

            block_of_sentences = carry_lines + block_of_sentences
            block_sentence_reference_ranges = carry_reference_ranges + block_sentence_reference_ranges

        range_start = block_sentence_reference_ranges[0] if block_sentence_reference_ranges else (0, 0)
        range_stop = block_sentence_reference_ranges[-1] if block_sentence_reference_ranges else (0, 0)
        logger.debug(f"Chunking block {block_index + 1}: {len(block_of_sentences)} sentences, range {range_start} to {range_stop}")

        chunk_result: ChunkSchema = chunk_callback(block_of_sentences)
        ranges = _chunk_start_to_ranges(chunk_result.chunk_start_lines, len(block_of_sentences))
        headers = chunk_result.headers

        block_chunks, carry = _extract_chunks_and_carry(block_of_sentences, ranges)

        for i, (r_start, r_end) in enumerate(ranges[:-1] if carry else ranges):
            r_reference_ranges = block_sentence_reference_ranges[r_start - 1:r_end - 1]
            r_range = _aggregate_ranges(r_reference_ranges)

            # DEBUG
            # logger.info(f"Chunk {len(chunks_with_ranges) + 1}: sentences {r_start}:{r_end}, range {r_range}")

            body = "\n".join(block_of_sentences[r_start - 1:r_end - 1])
            chunk_text = _format_chunk(
                file_path=file_path,
                header=headers[i],
                body=body,
            )

            chunks_with_ranges.append(ChunkWithRange(chunk_text, r_range))

        if carry:
            carry_reference_ranges = block_sentence_reference_ranges[ranges[-1][0] - 1:ranges[-1][1] - 1]
            last_carry_header = headers[-1]

    if carry:
        assert last_carry_header is not None, "Internal error: carry exists but no header was recorded"
        assert carry_reference_ranges is not None
        carry_lines = splitlines_exact(carry)
        final_chunk_line_count: int = len(carry_lines)

        if verbose:
            logger.info(f"Appending final carry of ({final_chunk_line_count}) lines; final chunk has ({final_chunk_line_count}) lines")

        formatted_carry = _format_chunk(
            file_path=file_path,
            header=last_carry_header,
            body=carry,
        )
        carry_range = _aggregate_ranges(carry_reference_ranges)
        chunks_with_ranges.append(ChunkWithRange(formatted_carry, carry_range))

    return chunks_with_ranges
