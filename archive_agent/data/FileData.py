#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import uuid
from typing import List

from qdrant_client.models import PointStruct

from archive_agent.data import ChunkManager
from archive_agent.openai_ import OpenAiManager
from archive_agent.util.image import is_image
from archive_agent.util.text import is_text, load_as_utf8

logger = logging.getLogger(__name__)


class FileData:
    """
    File data.
    """

    def __init__(
        self,
        openai: OpenAiManager,
        chunker: ChunkManager,
        file_path: str,
        file_mtime: float,
    ):
        """
        Initialize file data.
        :param chunker: Chunk manager.
        :param file_path: File path.
        :param file_mtime: File modification time.
        """
        self.openai = openai
        self.chunker = chunker
        self.file_path = file_path
        self.file_mtime = file_mtime

        self.text: str = ""
        self.points: List[PointStruct] = []

    @staticmethod
    def is_processable(file_path: str) -> bool:
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

    def decode(self) -> str:
        """
        Decode file data to text.
        :return: Text.
        """
        if is_image(self.file_path):
            return self.openai.vision(self.file_path)
        elif is_text(self.file_path):
            return load_as_utf8(self.file_path)
        else:
            logger.error(f"Cannot process file: '{self.file_path}'")
            raise typer.Exit(code=1)

    def process(self) -> None:
        """
        Process file data.
        """
        self.text = self.decode()

        chunks = self.chunker.get_chunks(self.text)

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
