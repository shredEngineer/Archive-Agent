# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import uuid
from typing import List, Optional, Dict, Any, Callable

from PIL import Image

from qdrant_client.models import PointStruct

from archive_agent.ai.AiManager import AiManager
from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.ai.vision.AiVisionEntity import AiVisionEntity
from archive_agent.ai.vision.AiVisionOCR import AiVisionOCR
from archive_agent.ai.vision.AiVisionSchema import VisionSchema
from archive_agent.config.DecoderSettings import DecoderSettings
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.format import format_file
from archive_agent.data.loader.pdf import is_pdf_document, load_pdf_document
from archive_agent.data.loader.image import is_image, load_image
from archive_agent.util.image_util import image_resize_safe, image_to_base64
from archive_agent.data.loader.text import is_plaintext, load_plaintext
from archive_agent.data.loader.text import is_ascii_document, load_ascii_document
from archive_agent.data.loader.text import is_binary_document, load_binary_document
from archive_agent.data.chunk import get_chunks_with_reference_ranges, get_sentences_with_reference_ranges


DecoderCallable = Callable[[], Optional[DocumentContent]]


class FileData:

    def __init__(
            self,
            ai: AiManager,
            decoder_settings: DecoderSettings,
            file_path: str,
            file_meta: Dict[str, Any],
    ):
        """
        Initialize file data.
        :param ai: AI manager instance.
        :param decoder_settings: Decoder settings.
        :param file_path: Path to the file.
        :param file_meta: File metadata.
        """
        self.ai = ai
        self.decoder_settings = decoder_settings

        self.chunk_lines_block = ai.chunk_lines_block

        self.file_path = file_path
        self.file_meta = file_meta

        self.points: List[PointStruct] = []

        self.image_to_text_callback_entity = self.image_to_text_entity if self.ai.ai_provider.supports_vision else None
        self.image_to_text_callback_ocr = self.image_to_text_ocr if self.ai.ai_provider.supports_vision else None

        if not self.decoder_settings.image_entity_extract:
            # Fallback to OCR when entity extraction is disabled
            self.image_to_text_callback_entity = self.image_to_text_callback_ocr

        self.decoder_func: Optional[DecoderCallable] = self.get_decoder_func()

    def get_decoder_func(self) -> Optional[DecoderCallable]:
        """
        Determine the appropriate decoder function based on file type.

        :return: Decoder function or None if unsupported.
        """
        if is_image(self.file_path):
            # Use entity extraction for image
            return lambda: load_image(
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback_entity,
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
            # Use entity extraction for image in binary document
            return lambda: load_binary_document(
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback_entity,
            )

        elif is_pdf_document(self.file_path):
            # Use OCR for PDF page
            return lambda: load_pdf_document(
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback_ocr,
                decoder_settings=self.decoder_settings,
            )

        return None

    def is_processable(self) -> bool:
        """
        Check if the file is processable based on decoder availability.

        :return: True if processable, False otherwise.
        """
        return self.decoder_func is not None

    def image_to_text(self, image: Image.Image) -> Optional[VisionSchema]:
        """
        Convert image to RGB if needed, resize, and process with AI vision.

        :param image: PIL Image object.
        :return: VisionSchema result or None if failed.
        """
        if image.mode != "RGB":
            self.ai.cli.logger.info(f"Converted image from '{image.mode}' to 'RGB'")
            image = image.convert("RGB")

        image_possibly_resized = image_resize_safe(image)
        if image_possibly_resized is None:
            self.ai.cli.logger.warning(f"Failed to resize {format_file(self.file_path)}")
            return None

        self.ai.cli.logger.info(f"Image dimensions: ({image_possibly_resized.width} × {image_possibly_resized.height} px)")

        image_base64 = image_to_base64(image_possibly_resized)

        vision_result = self.ai.vision(image_base64)

        if vision_result.is_rejected:
            self.ai.cli.logger.critical(f"⚠️  Image rejected: \"{vision_result.rejection_reason}\"")
            return None

        return vision_result

    def image_to_text_ocr(self, image: Image.Image) -> Optional[str]:
        """
        Request vision with OCR on the image and format the result.

        :param image: PIL Image object.
        :return: OCR text or None if failed.
        """
        self.ai.cli.logger.info("Requesting vision with OCR")
        self.ai.request_ocr()
        vision_result = self.image_to_text(image)
        if vision_result is not None:
            return AiVisionOCR.format_vision_answer(vision_result)
        else:
            return None

    def image_to_text_entity(self, image: Image.Image) -> Optional[str]:
        """
        Request vision with entity extraction on the image and format the result.

        :param image: PIL Image object.
        :return: Entity text or None if failed.
        """
        self.ai.cli.logger.info("Requesting vision with entity extraction")
        self.ai.request_entity()
        vision_result = self.image_to_text(image)
        if vision_result is not None:
            return AiVisionEntity.format_vision_answer(logger=self.ai.cli.logger, vision_result=vision_result)
        else:
            return None

    def decode(self) -> Optional[DocumentContent]:
        """
        Decode the file using the determined decoder function.

        :return: DocumentContent or None if failed or unsupported.
        """
        if self.decoder_func is not None:
            try:
                return self.decoder_func()
            except Exception as e:
                self.ai.cli.logger.warning(f"Failed to process {format_file(self.file_path)}: {e}")
                return None

        self.ai.cli.logger.warning(f"Cannot process {format_file(self.file_path)}")
        return None

    def chunk_callback(self, block_of_sentences: List[str]) -> ChunkSchema:
        """
        Callback for chunking a block of sentences using AI.

        :param block_of_sentences: List of sentences to chunk.
        :return: ChunkSchema result.
        """
        chunk_result = self.ai.chunk(block_of_sentences)

        return chunk_result

    def process(self) -> bool:
        """
        Process the file: decode, split, chunk, embed, and create points.

        :return: True if successful, False otherwise.
        """

        # TODO: Outsource call
        # Call the loader function assigned to this file data.
        # NOTE: DocumentContent is an array of text lines, mapped to page or line numbers.
        doc_content: Optional[DocumentContent] = self.decode()

        # Decoder may fail, e.g. on I/O error, exhausted AI attempts, …
        if doc_content is None:
            self.ai.cli.logger.warning(f"Failed to process {format_file(self.file_path)}")
            return False

        # ...
        is_page_based = doc_content.pages_per_line is not None
        if is_page_based:
            per_line_references = doc_content.pages_per_line
        else:
            per_line_references = doc_content.lines_per_line

        assert per_line_references is not None, "Missing references (WTF)"

        # TODO: Pass DocumentContent
        # Use preprocessing and NLP (spaCy) to split text into sentences, keeping track of references.
        sentences_with_reference_ranges = get_sentences_with_reference_ranges(doc_content.text, per_line_references)

        chunks = get_chunks_with_reference_ranges(
            sentences_with_references=sentences_with_reference_ranges,
            chunk_callback=self.chunk_callback,
            chunk_lines_block=self.chunk_lines_block,
            file_path=self.file_path
        )

        is_page_based = doc_content.pages_per_line is not None

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        for chunk_index, chunk in enumerate(chunks):
            self.ai.cli.logger.info(
                f"Processing chunk ({chunk_index + 1}) / ({len(chunks)}) "
                f"of {format_file(self.file_path)}"
            )

            if self.ai.cli.VERBOSE_CHUNK:
                reference_type = "Pages" if is_page_based else "Lines"
                self.ai.cli.logger.info(f"Reference range: {reference_type} {chunk.reference_range[0]}–{chunk.reference_range[1]}")

            vector = self.ai.embed(text=chunk.text)

            payload = {
                'file_path': self.file_path,
                'file_mtime': self.file_meta['mtime'],
                'chunk_index': chunk_index,
                'chunks_total': len(chunks),
                'chunk_text': chunk.text,
            }

            if chunk.reference_range != (0, 0):
                min_r, max_r = chunk.reference_range
                range_list = [min_r, max_r] if min_r != max_r else [min_r]
                if is_page_based:
                    payload['page_range'] = range_list
                else:
                    payload['line_range'] = range_list
            else:
                self.ai.cli.logger.warning("Missing reference range for chunk")

            self.points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload,
                )
            )

        return True
