#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import uuid
from typing import List, Optional

from PIL import Image

from qdrant_client.models import PointStruct

from archive_agent.ai.AiManager import AiManager
from archive_agent.util.image import is_image
from archive_agent.util.text import is_text, load_text, is_pdf_document
from archive_agent.util.pdf import load_pdf_document
from archive_agent.util.format import format_file
from archive_agent.util.text import split_sentences, sanitize_sentences, group_blocks_of_sentences
from archive_agent.util.image import image_from_file, image_resize_safe, image_to_base64

logger = logging.getLogger(__name__)


class FileData:
    """
    File data.
    """

    def __init__(
        self,
        ai: AiManager,
        file_path: str,
        file_mtime: float,
    ):
        """
        Initialize file data.
        :param ai: AI manager.
        :param file_path: File path.
        :param file_mtime: File modification time.
        """
        self.ai = ai
        self.chunk_lines_block = ai.chunk_lines_block

        self.file_path = file_path
        self.file_mtime = file_mtime

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

        elif is_pdf_document(file_path):
            return True

        else:
            return False

    def image_to_text(self, image: Image.Image) -> Optional[str]:
        """
        Convert image to text.
        :param image: Image.
        :return: Text if successful, None otherwise.
        """
        image_possibly_resized = image_resize_safe(image)
        if image_possibly_resized is None:
            logger.warning(f"Failed to resize {format_file(self.file_path)}")
            return None

        image_base64 = image_to_base64(image_possibly_resized)

        vision_result = self.ai.vision(image_base64)

        if vision_result.reject:
            logger.warning(f"Image rejected: {vision_result.rejection_reason}")
            return None

        return vision_result.answer

    def decode(self) -> Optional[str]:
        """
        Decode file data to text.
        :return: Text if successful, None otherwise.
        """
        if is_image(self.file_path):
            image = image_from_file(self.file_path)
            if image is None:
                logger.warning(f"Failed to load {format_file(self.file_path)}")
                return None

            return self.image_to_text(image)

        elif is_text(self.file_path):
            return load_text(self.file_path)

        elif is_pdf_document(self.file_path):
            return load_pdf_document(self.file_path, self.image_to_text)

        else:
            logger.warning(f"Cannot process {format_file(self.file_path)}")
            return None

    def chunks(self, text: str) -> List[str]:
        """
        Split text into chunks.
        :param text: Text.
        :return: Chunks.
        """
        sentences = sanitize_sentences(split_sentences(text))

        blocks_of_sentences = group_blocks_of_sentences(sentences, self.chunk_lines_block)

        chunks = []
        for block_index, block_of_sentences in enumerate(blocks_of_sentences):
            logger.info(
                f"Chunking block ({block_index + 1}) / ({len(blocks_of_sentences)}) "
                f"of {format_file(self.file_path)}"
            )

            chunk_result = self.ai.chunk(block_of_sentences)

            # Append a sentinel value to simplify range slicing
            start_lines = chunk_result.chunk_start_lines + [len(block_of_sentences) + 1]

            block_chunks = [
                "\n".join(block_of_sentences[start - 1:end - 1])
                for start, end in zip(start_lines, start_lines[1:])
            ]

            for i, chunk in enumerate(block_chunks):
                if len(chunk) > 5000:  # Adjust threshold as needed
                    logger.warning(
                        f"Chunk ({i + 1}) in block ({block_index + 1}) is very large: ({len(chunk)}) characters"
                    )

            chunks += block_chunks

        return chunks

    def process(self) -> bool:
        """
        Process file data.
        :return: True if successful, False otherwise.
        """
        text = self.decode()
        if text is None:
            logger.warning(f"Failed to process {format_file(self.file_path)}")
            return False

        chunks = self.chunks(text)

        for chunk_index, chunk in enumerate(chunks):
            logger.info(f"Processing chunk ({chunk_index + 1}) / ({len(chunks)}) of {format_file(self.file_path)}")

            vector = self.ai.embed(chunk)

            self.points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        'file_path': self.file_path,
                        'file_mtime': self.file_mtime,
                        'chunk_index': chunk_index,
                        'chunks_total': len(chunks),
                        'chunk_text': chunk,
                    },
                )
            )

        return True
