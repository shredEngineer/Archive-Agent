# archive_agent/data/FileData.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from archive_agent import __version__

import uuid
from typing import List, Optional, Dict, Any, Callable
from rich.progress import Progress

from PIL import Image

from qdrant_client.models import PointStruct
from archive_agent.db.QdrantSchema import QdrantPayload

from archive_agent.ai.AiManager import AiManager
from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.ai.vision.AiVisionEntity import AiVisionEntity
from archive_agent.ai.vision.AiVisionOCR import AiVisionOCR
from archive_agent.ai.vision.AiVisionSchema import VisionSchema
from archive_agent.config.DecoderSettings import DecoderSettings
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.format import format_file, get_point_page_line_info, format_filename_short
from archive_agent.data.loader.pdf import is_pdf_document, load_pdf_document
from archive_agent.data.loader.image import is_image, load_image
from archive_agent.data.loader.text import is_plaintext, load_plaintext
from archive_agent.data.loader.text import is_ascii_document, load_ascii_document
from archive_agent.data.loader.text import is_binary_document, load_binary_document
from archive_agent.util.image_util import image_resize_safe, image_to_base64
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

        self.logger = ai.cli.get_prefixed_logger(prefix=format_filename_short(self.file_path))

        self.points: List[PointStruct] = []

        self.image_to_text_callback_combined = self.image_to_text_combined if self.ai.ai_provider.supports_vision else None
        self.image_to_text_callback_entity = self.image_to_text_entity if self.ai.ai_provider.supports_vision else None
        self.image_to_text_callback_ocr = self.image_to_text_ocr if self.ai.ai_provider.supports_vision else None

        self.image_to_text_callback_page = self.image_to_text_callback_ocr

        if self.decoder_settings.image_ocr and self.decoder_settings.image_entity_extract:
            self.image_to_text_callback_image = self.image_to_text_callback_combined
        elif self.decoder_settings.image_ocr:
            self.image_to_text_callback_image = self.image_to_text_ocr
        elif self.decoder_settings.image_entity_extract:
            self.image_to_text_callback_image = self.image_to_text_callback_entity
        else:
            self.image_to_text_callback_image = None

        self.decoder_func: Optional[DecoderCallable] = self.get_decoder_func()

    def get_decoder_func(self) -> Optional[DecoderCallable]:
        """
        Determine the appropriate decoder function based on file type.

        :return: Decoder function or None if unsupported.
        """
        if is_image(self.file_path):
            return lambda: load_image(
                logger=self.logger,
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback_image,
            )

        elif is_plaintext(self.file_path):
            return lambda: load_plaintext(
                logger=self.logger,
                file_path=self.file_path,
            )

        elif is_ascii_document(self.file_path):
            return lambda: load_ascii_document(
                logger=self.logger,
                file_path=self.file_path,
            )

        elif is_binary_document(self.file_path):
            return lambda: load_binary_document(
                logger=self.logger,
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback_image,
            )

        elif is_pdf_document(self.file_path):
            return lambda: load_pdf_document(
                logger=self.logger,
                file_path=self.file_path,
                image_to_text_callback_page=self.image_to_text_callback_page,
                image_to_text_callback_image=self.image_to_text_callback_image,
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
            self.logger.info(f"Converted image from '{image.mode}' to 'RGB'")
            image = image.convert("RGB")

        image_possibly_resized = image_resize_safe(image=image, logger=self.logger)
        if image_possibly_resized is None:
            self.logger.warning(f"Failed to resize {format_file(self.file_path)}")
            return None

        image_base64 = image_to_base64(image_possibly_resized)

        vision_result = self.ai.vision(image_base64)

        if vision_result.is_rejected:
            self.logger.critical(f"⚠️ Image rejected: \"{vision_result.rejection_reason}\"")
            return None

        return vision_result

    def image_to_text_ocr(self, image: Image.Image) -> Optional[str]:
        """
        Request vision with OCR on the image and format the result.

        :param image: PIL Image object.
        :return: OCR text or None if failed.
        """
        self.logger.info("Requesting vision feature: OCR")
        self.ai.request_ocr()
        vision_result = self.image_to_text(image)
        if vision_result is not None:
            return AiVisionOCR.format_vision_answer(vision_result=vision_result)
        else:
            return None

    def image_to_text_entity(self, image: Image.Image) -> Optional[str]:
        """
        Request vision with entity extraction on the image and format the result.

        :param image: PIL Image object.
        :return: Entity text or None if failed.
        """
        self.logger.info("Requesting vision feature: Entity Extraction")
        self.ai.request_entity()
        vision_result = self.image_to_text(image)
        if vision_result is not None:
            return AiVisionEntity.format_vision_answer(vision_result=vision_result)
        else:
            return None

    def image_to_text_combined(self, image: Image.Image) -> Optional[str]:
        """
        Request vision with OCR and entity extraction on the image, format and join the results.
        :param image: PIL Image object.
        :return: Combined text or None if any part failed.
        """
        self.logger.info("Requesting vision features: OCR, Entity Extraction")

        self.ai.request_ocr()
        vision_result_ocr = self.image_to_text(image)
        if vision_result_ocr is None:
            return None
        text_ocr = AiVisionOCR.format_vision_answer(vision_result=vision_result_ocr)

        self.ai.request_entity()
        vision_result_entity = self.image_to_text(image)
        if vision_result_entity is None:
            return None
        text_entity = AiVisionEntity.format_vision_answer(vision_result=vision_result_entity)

        # Join with a single space
        return text_ocr + " " + text_entity

    def decode(self) -> Optional[DocumentContent]:
        """
        Decode the file using the determined decoder function.

        :return: DocumentContent or None if failed or unsupported.
        """
        if self.decoder_func is not None:
            try:
                return self.decoder_func()
            except Exception as e:
                self.logger.warning(f"Failed to process {format_file(self.file_path)}: {e}")
                return None

        self.logger.warning(f"Cannot process {format_file(self.file_path)}")
        return None

    def chunk_callback(self, block_of_sentences: List[str]) -> ChunkSchema:
        """
        Callback for chunking a block of sentences using AI.

        :param block_of_sentences: List of sentences to chunk.
        :return: ChunkSchema result.
        """
        chunk_result = self.ai.chunk(block_of_sentences)

        return chunk_result

    def process(self, progress: Optional[Progress] = None, task_id: Optional[Any] = None) -> bool:
        """
        Process the file: decode, split, chunk, embed, and create points.
        :param progress: A rich.progress.Progress object for progress reporting.
        :param task_id: The task ID for the progress bar.
        :return: True if successful, False otherwise.
        """

        # Call the loader function assigned to this file data.
        # NOTE: DocumentContent is an array of text lines, mapped to page or line numbers.
        doc_content: Optional[DocumentContent] = self.decode()

        # Decoder may fail, e.g. on I/O error, exhausted AI attempts, …
        if doc_content is None:
            self.logger.warning(f"Failed to process {format_file(self.file_path)}")
            return False

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        doc_content.strip_lines()

        # Use preprocessing and NLP (spaCy) to split text into sentences, keeping track of references.
        if self.ai.cli.VERBOSE_CHUNK:
            self.logger.info(f"Extracting sentences across ({len(doc_content.lines)}) lines")
        sentences_with_reference_ranges = get_sentences_with_reference_ranges(doc_content)

        # Group sentences into chunks, keeping track of references.
        if self.ai.cli.VERBOSE_CHUNK:
            self.logger.info(f"Extracting chunks across ({len(sentences_with_reference_ranges)}) sentences")
        chunks = get_chunks_with_reference_ranges(
            sentences_with_references=sentences_with_reference_ranges,
            chunk_callback=self.chunk_callback,
            chunk_lines_block=self.chunk_lines_block,
            file_path=self.file_path,
            logger=self.logger,
            verbose=self.ai.cli.VERBOSE_CHUNK,
        )

        is_page_based = doc_content.pages_per_line is not None

        if is_page_based:
            max_page = max(doc_content.pages_per_line) if doc_content.pages_per_line else 0
            reference_total_info = f"{max_page}"
        else:
            max_line = max(doc_content.lines_per_line) if doc_content.lines_per_line else 0
            reference_total_info = f"{max_line}"

        if progress and task_id:
            progress.update(task_id, total=len(chunks))

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        for chunk_index, chunk in enumerate(chunks):
            if self.ai.cli.VERBOSE_CHUNK:
                self.logger.info(
                    f"Processing chunk ({chunk_index + 1}) / ({len(chunks)}) "
                    f"of {format_file(self.file_path)}"
                )

            assert chunk.reference_range != (0, 0), "Invalid chunk reference range (WTF, please report)"

            vector = self.ai.embed(text=chunk.text)

            payload_model = QdrantPayload(
                file_path=self.file_path,
                file_mtime=self.file_meta['mtime'],
                chunk_index=chunk_index,
                chunks_total=len(chunks),
                chunk_text=chunk.text,
                version=f"v{__version__}",
                page_range=None,
                line_range=None,
            )

            min_r, max_r = chunk.reference_range
            range_list = [min_r, max_r] if min_r != max_r else [min_r]
            if is_page_based:
                payload_model.page_range = range_list
            else:
                payload_model.line_range = range_list

            payload = payload_model.model_dump()

            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            )

            if self.ai.cli.VERBOSE_CHUNK:
                self.logger.info(
                    f"Reference for chunk ({chunk_index + 1}) / ({len(chunks)}): "
                    f"{get_point_page_line_info(point)} "
                    f"of {reference_total_info}"
                )

            point.vector = vector

            self.points.append(point)

            if progress and task_id:
                progress.update(task_id, advance=1)

        return True
