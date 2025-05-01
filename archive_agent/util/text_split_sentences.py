#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List
import spacy
import re


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences while preserving paragraph structure.
    - Remove outer whitespace (leading/trailing) from each line
    - Preserve only true double newlines as paragraph boundaries
    - Normalize inline whitespace (multiple spaces, tabs, etc.)

    :param text: Text.
    :return: List of sentences. Empty strings represent paragraph breaks.
    """
    nlp = spacy.load("xx_sent_ud_sm")
    nlp.max_length = 100_000_000  # Allow very large documents
    if not nlp.has_pipe("sentencizer"):
        nlp.add_pipe("sentencizer")

    cleaned_text = _normalize_lines(text)
    paragraphs = cleaned_text.split("\n\n")

    sentences: List[str] = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            sentences.append("")  # Paragraph break
        else:
            sentences.extend(_paragraph_to_sentences(paragraph, nlp))
            sentences.append("")

    if sentences and sentences[-1] == "":
        sentences.pop()

    return sentences


def _normalize_lines(text: str) -> str:
    """
    Normalize the input text:
    - Strip outer whitespace from each line (leading/trailing spaces/tabs)
    - Keep only double newlines as paragraph boundaries (single newlines get flattened)
    - Force double newlines before markdown list items
    """
    stripped_lines = [line.strip() for line in text.splitlines()]

    paragraph_blocks: List[List[str]] = []
    current_block: List[str] = []

    for line in stripped_lines:
        if not line:
            if current_block:
                paragraph_blocks.append(current_block)
                current_block = []
        elif line.startswith("- "):
            # Close current paragraph before a list item
            if current_block:
                paragraph_blocks.append(current_block)
                current_block = []
            paragraph_blocks.append([line])  # List item becomes its own paragraph
        else:
            current_block.append(line)

    if current_block:
        paragraph_blocks.append(current_block)

    # Join lines inside paragraphs with space; join paragraphs with double newline
    normalized_paragraphs = [" ".join(block) for block in paragraph_blocks]
    return "\n\n".join(normalized_paragraphs)


def _paragraph_to_sentences(paragraph: str, nlp) -> List[str]:
    """
    Convert a flat paragraph string into a list of clean sentences.

    :param paragraph: One paragraph string
    :param nlp: spaCy NLP pipeline
    :return: List of sentences
    """
    # Step 3: Normalize inline whitespace (tabs, multiple spaces)
    paragraph = _normalize_inline_whitespace(paragraph)

    doc = nlp(paragraph)
    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]


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
