#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import uuid
from typing import List, Optional, Dict, Any, Callable

from PIL import Image

from qdrant_client.models import PointStruct

from archive_agent.ai.AiManager import AiManager
from archive_agent.config.DecoderSettings import DecoderSettings
from archive_agent.util.format import format_file
from archive_agent.util.pdf import is_pdf_document, load_pdf_document
from archive_agent.util.image import is_image, load_image
from archive_agent.util.image_util import image_resize_safe, image_to_base64
from archive_agent.util.chunk import split_into_blocks, chunk_start_to_ranges, extract_chunks_and_carry
from archive_agent.util.text import is_plaintext, load_plaintext
from archive_agent.util.text import is_ascii_document, load_ascii_document
from archive_agent.util.text import is_binary_document, load_binary_document

logger = logging.getLogger(__name__)


DecoderCallable = Callable[[], Optional[str]]


class FileData:
    """
    File data.
    """

    def __init__(
        self,
        ai: AiManager,
        decoder_settings: DecoderSettings,
        file_path: str,
        file_meta: Dict[str, Any],
    ):
        """
        Initialize file data.
        :param ai: AI manager.
        :param decoder_settings: Decoder settings.
        :param file_path: File path.
        :param file_meta: File metadata.
        """
        self.ai = ai
        self.decoder_settings = decoder_settings

        self.chunk_lines_block = ai.chunk_lines_block

        self.file_path = file_path
        self.file_meta = file_meta

        self.points: List[PointStruct] = []

        self.image_to_text_callback = self.image_to_text if self.ai.ai_provider.supports_vision else None

        self.decoder_func: Optional[DecoderCallable] = self.get_decoder_func()

    def get_decoder_func(self) -> Optional[DecoderCallable]:
        """
        Get decoder function for file.
        :return: Decoder function if available, None otherwise.
        """
        if is_image(self.file_path):
            return lambda: load_image(
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback,
            )

        elif is_plaintext(self.file_path):
            return lambda: load_plaintext(
                file_path=self.file_path,
            )

        elif is_ascii_document(self.file_path):
            return lambda: load_ascii_document(
                file_path=self.file_path,
            )

        elif is_binary_document(self.file_path):
            return lambda: load_binary_document(
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback,
            )

        elif is_pdf_document(self.file_path):
            return lambda: load_pdf_document(
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback,
                decoder_settings=self.decoder_settings,
            )

        else:
            return None

    def is_processable(self) -> bool:
        """
        Checks if the file is processable.
        :return: True if the file is processable, False otherwise.
        """
        return self.decoder_func is not None

    def image_to_text(self, image: Image.Image) -> Optional[str]:
        """
        Convert image to text.
        :param image: Image.
        :return: Text if successful, None otherwise.
        """

        if image.mode != "RGB":
            logger.info(f"Converted image from '{image.mode}' to 'RGB'")
            image = image.convert("RGB")

        image_possibly_resized = image_resize_safe(image)
        if image_possibly_resized is None:
            logger.warning(f"Failed to resize {format_file(self.file_path)}")
            return None

        logger.info(f"Image dimensions: ({image_possibly_resized.width} × {image_possibly_resized.height} px)")

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
        if self.decoder_func is not None:
            try:
                return self.decoder_func()
            except Exception as e:
                logger.warning(f"Failed to process {format_file(self.file_path)}: {e}")
                return None

        else:
            logger.warning(f"Cannot process {format_file(self.file_path)}")
            return None

    def chunks(self, text: str) -> List[str]:
        """
        Split text into chunks, with soft merging between block boundaries.
        :param text: Text.
        :return: Chunks.
        """
        blocks_of_sentences = split_into_blocks(text, self.chunk_lines_block)

        chunks: List[str] = []
        carry: Optional[str] = None

        for block_index, block_of_sentences in enumerate(blocks_of_sentences):
            logger.info(
                f"Chunking block ({block_index + 1}) / ({len(blocks_of_sentences)}) "
                f"of {format_file(self.file_path)}"
            )

            if carry:
                # `carry` is merged with the next block before chunking.
                current_block_line_count: int = len(carry.splitlines()) + len(block_of_sentences)
                logger.info(
                    f"Carrying over ({len(carry.splitlines())}) lines; "
                    f"current block has ({current_block_line_count}) lines"
                )
                block_of_sentences = carry.splitlines() + block_of_sentences

            chunk_result = self.ai.chunk(block_of_sentences)

            ranges = chunk_start_to_ranges(
                chunk_result.chunk_start_lines,
                len(block_of_sentences),
            )

            block_chunks, carry = extract_chunks_and_carry(
                block_of_sentences,
                ranges,
            )

            chunks += block_chunks

        if carry:
            final_chunk_line_count: int = len(carry.splitlines())
            logger.info(
                f"Appending final carry of ({final_chunk_line_count}) lines; "
                f"final chunk has ({final_chunk_line_count}) lines"
            )
            chunks.append(carry)

        return chunks

    def process(self) -> bool:
        """
        Process file data.
        :return: True if successful, False otherwise.
        """
        # TODO: Get {PDF page number : PDF line number} array and insert chunk's set of page numbers into chunk payload — see #15
        text = self.decode()
        if text is None:
            logger.warning(f"Failed to process {format_file(self.file_path)}")
            return False

        chunks = self.chunks(text)

        for chunk_index, chunk in enumerate(chunks):
            logger.info(f"Processing chunk ({chunk_index + 1}) / ({len(chunks)}) of {format_file(self.file_path)}")

            vector = self.ai.embed(text=chunk)

            self.points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        'file_path': self.file_path,
                        'file_mtime': self.file_meta['mtime'],
                        'chunk_index': chunk_index,
                        'chunks_total': len(chunks),
                        'chunk_text': chunk,
                    },
                )
            )

        return True
