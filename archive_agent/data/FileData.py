# archive_agent/data/FileData.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import logging
import uuid
from typing import List, Optional, Dict, Any, Callable

from PIL import Image

from qdrant_client.models import PointStruct

from archive_agent.ai.AiManager import AiManager
from archive_agent.config.DecoderSettings import DecoderSettings
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.format import format_file
from archive_agent.loader.pdf import is_pdf_document, load_pdf_document
from archive_agent.loader.image import is_image, load_image
from archive_agent.util.image_util import image_resize_safe, image_to_base64
from archive_agent.loader.text import is_plaintext, load_plaintext
from archive_agent.loader.text import is_ascii_document, load_ascii_document
from archive_agent.loader.text import is_binary_document, load_binary_document
from archive_agent.data.chunk import generate_chunks_with_ranges, split_sentences


logger = logging.getLogger(__name__)


DecoderCallable = Callable[[], Optional[DocumentContent]]


class FileData:

    def __init__(
            self,
            ai: AiManager,
            decoder_settings: DecoderSettings,
            file_path: str,
            file_meta: Dict[str, Any],
    ):
        self.ai = ai
        self.decoder_settings = decoder_settings

        self.chunk_lines_block = ai.chunk_lines_block

        self.file_path = file_path
        self.file_meta = file_meta

        self.points: List[PointStruct] = []

        self.image_to_text_callback = self.image_to_text if self.ai.ai_provider.supports_vision else None

        self.decoder_func: Optional[DecoderCallable] = self.get_decoder_func()

    def get_decoder_func(self) -> Optional[DecoderCallable]:
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

        return None

    def is_processable(self) -> bool:
        return self.decoder_func is not None

    def image_to_text(self, image: Image.Image) -> Optional[str]:
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

        if vision_result.is_rejected:
            logger.critical(f"Image rejected: {vision_result.rejection_reason}")

            # Immediately remove rejected AI result from cache.
            self.ai.ai_provider.cache.pop()

            return None

        return vision_result.answer

    def decode(self) -> Optional[DocumentContent]:
        if self.decoder_func is not None:
            try:
                return self.decoder_func()
            except Exception as e:
                logger.warning(f"Failed to process {format_file(self.file_path)}: {e}")
                return None

        logger.warning(f"Cannot process {format_file(self.file_path)}")
        return None

    def process(self) -> bool:
        doc_content = self.decode()
        if doc_content is None:
            logger.warning(f"Failed to process {format_file(self.file_path)}")
            return False

        per_line_references = doc_content.pages_per_line if doc_content.pages_per_line is not None else doc_content.lines_per_line or []
        sentences, sentence_reference_ranges = split_sentences(doc_content.text, per_line_references)

        chunks_with_ranges = generate_chunks_with_ranges(
            sentences=sentences,
            sentence_reference_ranges=sentence_reference_ranges,
            ai=self.ai,
            chunk_lines_block=self.chunk_lines_block,
            file_path=self.file_path
        )

        is_page_based = doc_content.pages_per_line is not None

        for chunk_index, chunk_with_range in enumerate(chunks_with_ranges):
            logger.info(f"Processing chunk ({chunk_index + 1}) / ({len(chunks_with_ranges)}) of {format_file(self.file_path)}")

            vector = self.ai.embed(text=chunk_with_range.text)

            payload = {
                'file_path': self.file_path,
                'file_mtime': self.file_meta['mtime'],
                'chunk_index': chunk_index,
                'chunks_total': len(chunks_with_ranges),
                'chunk_text': chunk_with_range.text,
            }

            chunk_range = chunk_with_range.reference_range
            if chunk_range != (0, 0):
                min_r, max_r = chunk_range
                range_list = [min_r, max_r] if min_r != max_r else [min_r]
                if is_page_based:
                    payload['page_range'] = range_list
                else:
                    payload['line_range'] = range_list

            self.points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload,
                )
            )

        return True
