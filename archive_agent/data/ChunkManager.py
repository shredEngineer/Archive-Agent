#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from nltk.tokenize import sent_tokenize

from archive_agent.openai_ import OpenAiManager
from archive_agent.util.text import ensure_nltk_punkt

logger = logging.getLogger(__name__)


class ChunkManager:
    """
    Chunk manager.
    """

    def __init__(
        self,
        openai: OpenAiManager,
        sentences_max: int,
    ):
        """
        Initialize chunk manager.
        :param openai: OpenAI manager.
        :param sentences_max: Maximum number of sentences per chunk.
        """
        self.openai = openai
        self.sentences_max = sentences_max

        ensure_nltk_punkt()

    def process(self, text: str) -> List[str]:
        """
        Process text into multiple chunks of a maximum number of sentences.
        :param text: Text.
        :return: List of chunks.
        """
        sentences = sent_tokenize(text)
        chunks = [
            ' '.join(sentences[i:i + self.sentences_max])
            for i in range(0, len(sentences), self.sentences_max)
        ]

        return chunks
