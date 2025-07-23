# archive_agent/data/chunk.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import logging
import re
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass

import spacy
from spacy import Language  # type: ignore
import bisect

from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.util.format import format_file

logger = logging.getLogger(__name__)

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


def _build_para_blocks(stripped_lines: List[str], per_line_references: ReferenceList) -> List[Tuple[List[str], ReferenceList]]:
    """
    Build paragraph blocks from stripped lines, respecting empty lines and Markdown list items.

    :param stripped_lines: List of stripped input lines.
    :param per_line_references: Per-line reference numbers (lines or pages).
    :return: List of (paragraph lines, associated refs) tuples.
    """
    para_blocks: List[Tuple[List[str], ReferenceList]] = []
    current_para: List[str] = []
    current_refs: ReferenceList = []
    has_references = bool(per_line_references)
    for i, line in enumerate(stripped_lines):
        if not line:
            # Paragraph handling: Close current block on empty line
            if current_para:
                para_blocks.append((current_para, current_refs))
                current_para = []
                current_refs = []
            continue

        if line.startswith("- "):
            # Markdown item handling: Treat list item as new paragraph block
            if current_para:
                para_blocks.append((current_para, current_refs))
                current_para = []
                current_refs = []
            current_para.append(line)
            if has_references:
                ref = per_line_references[i] if i < len(per_line_references) else 0
                current_refs.append(ref)
        else:
            current_para.append(line)
            if has_references:
                ref = per_line_references[i] if i < len(per_line_references) else 0
                current_refs.append(ref)

    if current_para:
        para_blocks.append((current_para, current_refs))

    return para_blocks


def _normalize_inline_whitespace(text: str) -> str:
    """
    Normalize inline whitespace inside a string:
    - Replace tabs and non-breaking spaces with normal space
    - Collapse multiple spaces into one

    :param text: Single paragraph string
    :return: Cleaned inline text
    """
    text = text.replace("\t", " ").replace("\xa0", " ")
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _process_para_block(
    para_lines: List[str],
    para_refs: ReferenceList,
    nlp: Language
) -> List[SentenceWithRange]:
    """
    Process a single paragraph block: Normalize, sentencize, and compute ranges.

    :param para_lines: Lines in the paragraph.
    :param para_refs: Associated line references.
    :param nlp: spaCy NLP pipeline.
    :return: List of SentenceWithRange for the block.
    """
    if not para_lines:
        return []  # Skip empty blocks

    normalized_lines = [_normalize_inline_whitespace(line) for line in para_lines]
    para_text = " ".join(normalized_lines)

    line_starts: Optional[List[int]] = None
    if para_refs:
        line_starts = [0]
        for norm_line in normalized_lines[:-1]:
            line_starts.append(line_starts[-1] + len(norm_line) + 1)

    doc = nlp(para_text)

    block_sentences: List[SentenceWithRange] = []

    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text:
            continue

        if para_refs and line_starts:
            start_char = sent.start_char
            end_char = sent.end_char

            start_line_idx = bisect.bisect_right(line_starts, start_char) - 1
            start_line_idx = min(start_line_idx, len(para_lines) - 1)

            end_line_idx = bisect.bisect_right(line_starts, end_char - 1) - 1
            end_line_idx = min(end_line_idx, len(para_lines) - 1)

            sent_refs = para_refs[start_line_idx: end_line_idx + 1]
            min_ref = min(sent_refs) if sent_refs else 0
            max_ref = max(sent_refs) if sent_refs else 0
        else:
            min_ref = max_ref = 0

        block_sentences.append(SentenceWithRange(sent_text, (min_ref, max_ref)))

    return block_sentences


# noinspection PyDefaultArgument
def split_sentences(text: str, per_line_references: ReferenceList = []) -> List[SentenceWithRange]:
    """
    Split text into sentences and assign per-sentence reference ranges.

    Processes text with paragraph and sentence handling, inferring ranges from provided references (lines or pages)
    if available, or defaulting to (0, 0).

    :param text: Input text (arbitrary, may have blank lines).
    :param per_line_references: Per-line reference numbers (e.g., absolute line or page numbers).
    :return: List of SentenceWithRange (text and range pairs).
    """
    lines = text.splitlines()
    stripped_lines = [line.strip() for line in lines]

    nlp = spacy.load("xx_sent_ud_sm")
    nlp.max_length = 100_000_000
    if not nlp.has_pipe("sentencizer"):
        nlp.add_pipe("sentencizer")

    para_blocks = _build_para_blocks(stripped_lines, per_line_references)

    sentences_with_ranges: List[SentenceWithRange] = []

    for i, (para_lines, para_refs) in enumerate(para_blocks):
        # Paragraph handling: Insert empty string and zero range for breaks before subsequent paragraphs
        if i > 0:
            sentences_with_ranges.append(SentenceWithRange("", (0, 0)))

        block_sentences = _process_para_block(para_lines, para_refs, nlp)
        sentences_with_ranges.extend(block_sentences)

    return sentences_with_ranges


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
    return (r_min, r_max)


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


def generate_chunks_with_ranges(
    sentences_with_ranges: List[SentenceWithRange],
    chunk_callback: Callable[[List[str]], ChunkSchema],
    chunk_lines_block: int,
    file_path: str
) -> List[ChunkWithRange]:
    """
    Chunkify a list of sentences into AI-determined chunks, carrying over leftover sentences where needed,
    and annotate each chunk with the corresponding (min, max) line reference range.

    :param sentences_with_ranges: List of sentences with their reference ranges.
    :param chunk_callback: Chunk callback.
    :param chunk_lines_block: Number of sentences per block to be chunked.
    :param file_path: Path to the originating file (used for logging and labeling).
    :return: List of ChunkWithRange objects containing the formatted chunk and its reference range.
    """
    sentences = [s.text for s in sentences_with_ranges]
    sentence_reference_ranges = [s.reference_range for s in sentences_with_ranges]

    if len(sentence_reference_ranges) != len(sentences):
        logger.error(
            f"Reference range mismatch: "
            f"{len(sentence_reference_ranges)} ranges, "
            f"{len(sentences)} sentences "
            f"for {format_file(file_path)}"
        )
        raise ValueError("Reference range mismatch")

    blocks_of_sentences = _group_blocks_of_sentences(sentences, chunk_lines_block)

    chunks_with_ranges: List[ChunkWithRange] = []
    carry: Optional[str] = None
    carry_range: SentenceRange = (0, 0)
    last_carry_header: Optional[str] = None

    idx = 0
    for block_index, block_of_sentences in enumerate(blocks_of_sentences):
        block_len = len(block_of_sentences)
        block_sentence_reference_ranges = sentence_reference_ranges[idx: idx + block_len]
        idx += block_len

        logger.info(f"Chunking block ({block_index + 1}) / ({len(blocks_of_sentences)}) of {format_file(file_path)}")

        if carry:
            current_block_line_count: int = len(carry.splitlines()) + len(block_of_sentences)
            logger.info(f"Carrying over ({len(carry.splitlines())}) lines; current block has ({current_block_line_count}) lines")
            block_of_sentences = carry.splitlines() + block_of_sentences
            block_sentence_reference_ranges = [carry_range] + block_sentence_reference_ranges

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

            logger.info(f"Chunk {len(chunks_with_ranges) + 1}: sentences {r_start}:{r_end}, range {r_range}")

            body = "\n".join(block_of_sentences[r_start - 1:r_end - 1])
            chunk_text = _format_chunk(
                file_path=file_path,
                header=headers[i],
                body=body,
            )

            chunks_with_ranges.append(ChunkWithRange(chunk_text, r_range))

        if carry:
            carry_reference_ranges = block_sentence_reference_ranges[ranges[-1][0] - 1:ranges[-1][1] - 1]
            carry_range = _aggregate_ranges(carry_reference_ranges)

            last_carry_header = headers[-1]

    if carry:
        assert last_carry_header is not None, "Internal error: carry exists but no header was recorded"
        final_chunk_line_count: int = len(carry.splitlines())
        logger.info(f"Appending final carry of ({final_chunk_line_count}) lines; final chunk has ({final_chunk_line_count}) lines")
        formatted_carry = _format_chunk(
            file_path=file_path,
            header=last_carry_header,
            body=carry,
        )
        chunks_with_ranges.append(ChunkWithRange(formatted_carry, carry_range))

    return chunks_with_ranges
