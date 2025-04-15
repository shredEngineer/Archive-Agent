#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import re
import tempfile
import urllib.parse
from typing import List

import spacy


def utf8_tempfile(text: str, suffix: str) -> str:
    """
    Write UTF-8 text into a temporary file.
    :param text: Text.
    :param suffix: File extension.
    :return: Temporary file path.
    """
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, delete=False) as tmp:
        tmp.write(text)
        return tmp.name


def replace_file_uris_with_markdown(text: str) -> str:
    """
    Replace file:// URIs with Markdown links.
    :param text: Text.
    :return: Markdown.
    """
    pattern = re.compile(r'file://[^\s\])]+')

    def replacer(match):
        uri = match.group(0)
        decoded_path = urllib.parse.unquote(uri.replace('file://', ''))
        return f'[{decoded_path}]({uri})'

    return pattern.sub(replacer, text)


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences.
    All lines are joined into a single paragraph before splitting.
    This avoids SpaCy treating line breaks as hard sentence stops.
    :param text: Text.
    :return: Sentences.
    """
    nlp = spacy.load("xx_sent_ud_sm")
    if not nlp.has_pipe("sentencizer"):
        nlp.add_pipe("sentencizer")

    # Join all non-empty lines with a space, flattening paragraphs.
    flat_text = " ".join(line.strip() for line in text.splitlines() if line.strip())

    doc = nlp(flat_text)
    sentences = [sent.text.strip() for sent in doc.sents]
    return sentences


def group_blocks_of_sentences(sentences: List[str], sentences_per_block: int) -> List[List[str]]:
    """
    Group sentences into blocks of multiple sentences.
    :param sentences: Sentences.
    :param sentences_per_block: Sentences per block.
    :return: Blocks of multiple sentences.
    """
    return [
        sentences[i:i + sentences_per_block]
        for i in range(0, len(sentences), sentences_per_block)
    ]


def prepend_line_numbers(sentences: List[str]) -> List[str]:
    """
    Prepend line numbers to sentences.
    :param sentences: Sentences.
    :return: Sentences with line numbers.
    """
    return [
        f"{line_number + 1:<4}{sentence}"
        for line_number, sentence in enumerate(sentences)
    ]
