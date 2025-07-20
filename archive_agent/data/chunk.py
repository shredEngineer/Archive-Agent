# archive_agent/data/chunk.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import logging
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

import spacy
import bisect

from archive_agent.ai.AiManager import AiManager
from archive_agent.util.format import format_file

logger = logging.getLogger(__name__)

SentenceRange = Tuple[int, int]


@dataclass
class ChunkWithRange:
    text: str
    reference_range: Tuple[int, int]


def chunk_start_to_ranges(start_lines: List[int], total_lines: int) -> List[SentenceRange]:
    extended = start_lines + [total_lines + 1]
    return list(zip(extended[:-1], extended[1:]))


def extract_chunks_and_carry(sentences: List[str], ranges: List[SentenceRange]) -> Tuple[List[str], str | None]:
    if not ranges:
        return [], None

    if len(ranges) == 1:
        start, end = ranges[0]
        return [], "\n".join(sentences[start - 1:end - 1])

    *main, last = ranges
    chunks = ["\n".join(sentences[start - 1:end - 1]) for start, end in main]
    carry = "\n".join(sentences[last[0] - 1:last[1] - 1])
    return chunks, carry


def group_blocks_of_sentences(sentences: List[str], sentences_per_block: int) -> List[List[str]]:
    return [sentences[i:i + sentences_per_block] for i in range(0, len(sentences), sentences_per_block)]


def split_sentences(text: str, per_line_references: List[int] = []) -> Tuple[List[str], List[Tuple[int, int]]]:
    """
    Split text into sentences and assign per-sentence reference ranges.

    For line-based sources (plaintext), if per_line_references matches the number of lines,
    perform a direct line-to-sentence mapping (no sentence segmentation or paragraph merging).
    Otherwise, fall back to advanced paragraph/sentence handling with reference inference.

    :param text: Input text (arbitrary, may have blank lines).
    :param per_line_references: Per-line reference numbers (e.g., absolute line or page numbers).
    :return: (sentences, per-sentence reference ranges).
    """
    lines = text.splitlines()

    # Fast-path: Line-based mapping (one sentence per line, direct mapping).
    if per_line_references and len(per_line_references) == len(lines):
        # Only return non-blank lines as sentences (mirroring previous logic).
        output_sentences = []
        output_ranges = []
        for line, ref in zip(lines, per_line_references):
            if line.strip():
                output_sentences.append(line.strip())
                output_ranges.append((ref, ref))
        return output_sentences, output_ranges

    # --- Original advanced paragraph/sentence logic below ---
    nlp = spacy.load("xx_sent_ud_sm")
    nlp.max_length = 100_000_000
    if not nlp.has_pipe("sentencizer"):
        nlp.add_pipe("sentencizer")

    stripped_lines = [line.strip() for line in lines]

    para_blocks: List[Tuple[List[str], List[int]]] = []
    current_para: List[str] = []
    current_refs: List[int] = []
    has_references = bool(per_line_references)
    for i, line in enumerate(stripped_lines):
        if not line:
            if current_para:
                para_blocks.append((current_para, current_refs))
                current_para = []
                current_refs = []
            continue

        if line.startswith("- "):
            if current_para:
                para_blocks.append((current_para, current_refs))
                current_para = []
                current_refs = []
            current_para.append(line)
            if has_references:
                current_refs.append(per_line_references[i])
        else:
            current_para.append(line)
            if has_references:
                current_refs.append(per_line_references[i])

    if current_para:
        para_blocks.append((current_para, current_refs))

    sentences: List[str] = []
    sentence_ranges: List[Tuple[int, int]] = []

    for para_lines, para_refs in para_blocks:
        if not para_lines:
            continue  # REMOVE dummy "" sentence/range

        normalized_lines = [_normalize_inline_whitespace(line) for line in para_lines]
        para_text = " ".join(normalized_lines)

        line_starts: Optional[List[int]] = None
        if para_refs:
            line_starts = [0]
            for norm_line in normalized_lines[:-1]:
                line_starts.append(line_starts[-1] + len(norm_line) + 1)

        doc = nlp(para_text)

        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue

            if para_refs:
                start_char = sent.start_char
                end_char = sent.end_char

                start_line_idx = bisect.bisect_right(line_starts, start_char) - 1  # type: ignore
                start_line_idx = min(start_line_idx, len(para_lines) - 1)

                end_line_idx = bisect.bisect_right(line_starts, end_char - 1) - 1  # type: ignore
                end_line_idx = min(end_line_idx, len(para_lines) - 1)

                sent_refs = para_refs[start_line_idx: end_line_idx + 1]
                min_ref = min(sent_refs) if sent_refs else 0
                max_ref = max(sent_refs) if sent_refs else 0
            else:
                min_ref = max_ref = 0

            sentences.append(sent_text)
            sentence_ranges.append((min_ref, max_ref))

    return sentences, sentence_ranges


def get_sentences(text: str) -> List[str]:
    sentences, _ = split_sentences(text)
    return sentences


def _normalize_inline_whitespace(text: str) -> str:
    text = text.replace("\t", " ").replace("\xa0", " ")
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def format_chunk(file_path: str, header: str, body: str):
    """
    Format chunk.
    :param file_path: File path.
    :param header: Chunk header.
    :param body: Chunk body.
    :return: Formatted chunk.
    """
    return "\n".join([
        f"# {format_file(file_path)}",
        f"# {header}",
        f"",
        body,
    ])


def generate_chunks_with_ranges(
        sentences: List[str],
        sentence_reference_ranges: List[Tuple[int, int]],
        ai: AiManager,
        chunk_lines_block: int,
        file_path: str
) -> List[ChunkWithRange]:
    if len(sentence_reference_ranges) != len(sentences):
        logger.error(
            f"Reference range mismatch: "
            f"{len(sentence_reference_ranges)} ranges, "
            f"{len(sentences)} sentences "
            f"for {format_file(file_path)}"
        )
        raise ValueError("Reference range mismatch")

    blocks_of_sentences = group_blocks_of_sentences(sentences, chunk_lines_block)

    chunks_with_ranges: List[ChunkWithRange] = []
    carry: Optional[str] = None
    carry_min: int = 0
    carry_max: int = 0

    idx = 0
    for block_index, block_of_sentences in enumerate(blocks_of_sentences):
        block_len = len(block_of_sentences)
        block_sentence_reference_ranges = sentence_reference_ranges[idx: idx+block_len]
        idx += block_len

        logger.info(f"Chunking block ({block_index + 1}) / ({len(blocks_of_sentences)}) of {format_file(file_path)}")

        if carry:
            current_block_line_count: int = len(carry.splitlines()) + len(block_of_sentences)
            logger.info(f"Carrying over ({len(carry.splitlines())}) lines; current block has ({current_block_line_count}) lines")
            block_of_sentences = carry.splitlines() + block_of_sentences
            block_sentence_reference_ranges = [(carry_min, carry_max)] + block_sentence_reference_ranges

        range_start = block_sentence_reference_ranges[0] if block_sentence_reference_ranges else (0, 0)
        range_stop = block_sentence_reference_ranges[-1] if block_sentence_reference_ranges else (0, 0)
        logger.debug(f"Chunking block {block_index + 1}: {len(block_of_sentences)} sentences, range {range_start} to {range_stop}")

        chunk_result = ai.chunk(block_of_sentences)
        ranges = chunk_start_to_ranges(chunk_result.chunk_start_lines, len(block_of_sentences))
        headers = chunk_result.headers

        block_chunks, carry = extract_chunks_and_carry(block_of_sentences, ranges)

        for i, (r_start, r_end) in enumerate(ranges[:-1] if carry else ranges):
            r_reference_ranges = block_sentence_reference_ranges[r_start - 1:r_end - 1]

            valid_mins = [min_r for min_r, _ in r_reference_ranges if min_r > 0]
            valid_maxs = [max_r for _, max_r in r_reference_ranges if max_r > 0]
            r_min = min(valid_mins) if valid_mins else 0
            r_max = max(valid_maxs) if valid_maxs else 0

            logger.info(f"Chunk {len(chunks_with_ranges) + 1}: sentences {r_start}:{r_end}, range ({r_min}, {r_max})")

            body = f"\n".join(block_of_sentences[r_start - 1:r_end - 1])
            chunk = format_chunk(
                file_path=file_path,
                header=headers[i],
                body=body,
            )

            chunks_with_ranges.append(ChunkWithRange(chunk, (r_min, r_max)))

        if carry:
            carry_reference_ranges = block_sentence_reference_ranges[ranges[-1][0] - 1:ranges[-1][1] - 1]

            valid_mins = [min_r for min_r, _ in carry_reference_ranges if min_r > 0]
            valid_maxs = [max_r for _, max_r in carry_reference_ranges if max_r > 0]
            carry_min = min(valid_mins) if valid_mins else 0
            carry_max = max(valid_maxs) if valid_maxs else 0

    if carry:
        final_chunk_line_count: int = len(carry.splitlines())
        logger.info(f"Appending final carry of ({final_chunk_line_count}) lines; final chunk has ({final_chunk_line_count}) lines")
        formatted_carry = format_chunk(
            file_path=file_path,
            header="Continuation Chunk",
            body=carry,
        )
        chunks_with_ranges.append(ChunkWithRange(formatted_carry, (carry_min, carry_max)))

    return chunks_with_ranges
