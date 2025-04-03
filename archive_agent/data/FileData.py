#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import uuid
from typing import List
from dataclasses import dataclass, field

import typer
from nltk.tokenize import sent_tokenize

from qdrant_client.models import PointStruct

from archive_agent.openai_ import OpenAiManager
from archive_agent.util.image import is_image
from archive_agent.util.text import is_text, load_as_utf8, ensure_nltk_punkt

logger = logging.getLogger(__name__)


@dataclass
class FileData:
    openai: OpenAiManager
    file_path: str
    file_mtime: float

    text: str = ""
    points: List[PointStruct] = field(default_factory=list)

    CHUNK_SENTENCES_MAX: int = 5

    @staticmethod
    def is_processable(file_path: str):
        """
        Checks if the given file path is processable.
        :param file_path: File path.
        :return: True if the file path is processable, False otherwise.
        """
        if is_image(file_path):
            return True
        elif is_text(file_path):
            return True
        else:
            return False

    def process(self) -> None:
        """
        Process file data.
        """
        if is_image(self.file_path):
            self.text = self.openai.vision(self.file_path)
        elif is_text(self.file_path):
            self.text = load_as_utf8(self.file_path)
        else:
            logger.error(f"Cannot process file: '{self.file_path}'")
            raise typer.Exit(code=1)

        chunks = self.get_chunks()

        for chunk_index, chunk in enumerate(chunks):

            logger.info(f" - Embedding file chunk ({chunk_index + 1}) / ({len(chunks)})...")

            total_tokens, vector = self.openai.embed(chunk)

            logger.info(f"   - Used ({total_tokens}) token(s)")

            payload = {
                'file_path': self.file_path,
                'file_mtime': self.file_mtime,
                'chunk_index': chunk_index,
                'chunks_total': len(chunks),
                'chunk': chunk,
            }
            self.points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload,
                )
            )

    def get_chunks(self) -> List[str]:
        """
        Split text into chunks of multiple sentences.
        :return: List of chunks.
        """
        ensure_nltk_punkt()

        sentences = sent_tokenize(self.text)
        chunks = [
            ' '.join(sentences[i:i + self.CHUNK_SENTENCES_MAX])
            for i in range(0, len(sentences), self.CHUNK_SENTENCES_MAX)
        ]
        return chunks
