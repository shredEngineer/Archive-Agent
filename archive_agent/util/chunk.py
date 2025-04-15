#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List, Tuple

from archive_agent.util.text_util import split_sentences, group_blocks_of_sentences

SentenceRange = Tuple[int, int]


def split_into_blocks(text: str, lines_per_block: int) -> List[List[str]]:
    """
    Split text into blocks of sentences.
    :param text: Raw text.
    :param lines_per_block: Number of lines per block.
    :return: List of blocks (each block is a list of sentences).
    """
    sentences = split_sentences(text)
    return group_blocks_of_sentences(sentences, lines_per_block)


def chunk_start_to_ranges(start_lines: List[int], total_lines: int) -> List[SentenceRange]:
    """
    Convert chunk start lines to (start, end) index pairs.

    :param start_lines: List of 1-based start line numbers.
    :param total_lines: Total number of lines in the block.
    :return: List of (start, end) pairs.
    """
    extended = start_lines + [total_lines + 1]
    return list(zip(extended[:-1], extended[1:]))


def extract_chunks_and_carry(sentences: List[str], ranges: List[SentenceRange]) -> Tuple[List[str], str | None]:
    """
    Extract all chunks except the last one. Return the last chunk as carry.

    :param sentences: List of sentences.
    :param ranges: Chunk start-end pairs (1-based).
    :return: Tuple of (main chunks, final chunk as carry).
    """
    if not ranges:
        return [], None

    if len(ranges) == 1:
        start, end = ranges[0]
        return [], "\n".join(sentences[start - 1:end - 1])

    *main, last = ranges
    chunks = [
        "\n".join(sentences[start - 1:end - 1])
        for start, end in main
    ]
    carry = "\n".join(sentences[last[0] - 1:last[1] - 1])
    return chunks, carry
