# archive_agent/data/FileData.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from archive_agent import __version__

import uuid
from typing import List, Optional, Dict, Callable, Any

from archive_agent.core.ProgressManager import ProgressManager, ProgressInfo

from PIL import Image

from qdrant_client.models import PointStruct

from archive_agent.data.processor.EmbedProcessor import EmbedProcessor
from archive_agent.db.QdrantSchema import QdrantPayload

from archive_agent.ai.AiManager import AiManager
from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.ai.vision.AiVisionEntity import AiVisionEntity
from archive_agent.ai.vision.AiVisionOCR import AiVisionOCR
from archive_agent.ai.vision.AiVisionSchema import VisionSchema
from archive_agent.config.DecoderSettings import DecoderSettings
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.format import get_point_page_line_info, format_filename_short
from archive_agent.data.loader.pdf import is_pdf_document, load_pdf_document
from archive_agent.data.loader.image import is_image, load_image
from archive_agent.data.loader.text import is_plaintext, load_plaintext
from archive_agent.data.loader.text import is_ascii_document, load_ascii_document
from archive_agent.data.loader.text import is_binary_document, load_binary_document
from archive_agent.util.image_util import image_resize_safe, image_to_base64
from archive_agent.data.chunk import get_chunks_with_reference_ranges, get_sentences_with_reference_ranges


DecoderCallable = Callable[[ProgressInfo], Optional[DocumentContent]]


class FileData:

    def __init__(
            self,
            ai_factory: AiManagerFactory,
            decoder_settings: DecoderSettings,
            file_path: str,
            file_meta: Dict[str, Any],
            max_workers_vision: int,
            max_workers_embed: int,
    ):
        """
        Initialize file data.
        :param ai_factory: AI manager factory for creating instances.
        :param decoder_settings: Decoder settings.
        :param file_path: Path to the file.
        :param file_meta: File metadata.
        :param max_workers_vision: Max. workers for vision.
        :param max_workers_embed: Max. workers for embedding.
        """
        # Core dependencies and configuration
        self.ai_factory = ai_factory
        self.ai = ai_factory.get_ai()  # Primary AI instance for vision, chunking, config
        self.decoder_settings = decoder_settings
        self.chunk_lines_block = self.ai.chunk_lines_block
        self.max_workers_vision = max_workers_vision
        self.max_workers_embed = max_workers_embed

        # File metadata and logging
        self.file_path = file_path
        self.file_meta = file_meta
        self.logger = self.ai.cli.get_prefixed_logger(prefix=format_filename_short(self.file_path))

        # Processing components
        self.chunk_processor = EmbedProcessor(ai_factory, self.logger, file_path, self.max_workers_embed)
        self.points: List[PointStruct] = []

        # Vision callback configuration based on AI provider capabilities
        self.image_to_text_callback_combined = self.image_to_text_combined if self.ai.ai_provider.supports_vision else None
        self.image_to_text_callback_entity = self.image_to_text_entity if self.ai.ai_provider.supports_vision else None
        self.image_to_text_callback_ocr = self.image_to_text_ocr if self.ai.ai_provider.supports_vision else None
        self.image_to_text_callback_page = self.image_to_text_callback_ocr

        # Select appropriate vision callback based on decoder settings
        if self.decoder_settings.image_ocr and self.decoder_settings.image_entity_extract:
            self.image_to_text_callback_image = self.image_to_text_callback_combined
        elif self.decoder_settings.image_ocr:
            self.image_to_text_callback_image = self.image_to_text_ocr
        elif self.decoder_settings.image_entity_extract:
            self.image_to_text_callback_image = self.image_to_text_callback_entity
        else:
            self.image_to_text_callback_image = None

        # Determine decoder function based on file type
        self.decoder_func: Optional[DecoderCallable] = self.get_decoder_func()

    def get_decoder_func(self) -> Optional[DecoderCallable]:
        """
        Determine the appropriate decoder function based on file type.

        :return: Decoder function or None if unsupported.
        """
        if is_image(self.file_path):
            return lambda progress_info: load_image(
                ai_factory=self.ai_factory,
                logger=self.logger,
                file_path=self.file_path,
                image_to_text_callback=self.image_to_text_callback_image,
                progress_info=progress_info,
            )

        elif is_plaintext(self.file_path):
            return lambda progress_info: load_plaintext(
                logger=self.logger,
                file_path=self.file_path,
            )

        elif is_ascii_document(self.file_path):
            return lambda progress_info: load_ascii_document(
                logger=self.logger,
                file_path=self.file_path,
            )

        elif is_binary_document(self.file_path):
            return lambda progress_info: load_binary_document(
                ai_factory=self.ai_factory,
                logger=self.logger,
                verbose=self.ai.cli.VERBOSE_LOADER,
                file_path=self.file_path,
                max_workers_vision=self.max_workers_vision,
                image_to_text_callback=self.image_to_text_callback_image,
                progress_info=progress_info,
            )

        elif is_pdf_document(self.file_path):
            return lambda progress_info: load_pdf_document(
                ai_factory=self.ai_factory,
                logger=self.logger,
                verbose=self.ai.cli.VERBOSE_LOADER,
                file_path=self.file_path,
                max_workers_vision=self.max_workers_vision,
                image_to_text_callback_page=self.image_to_text_callback_page,
                image_to_text_callback_image=self.image_to_text_callback_image,
                decoder_settings=self.decoder_settings,
                progress_info=progress_info,
            )

        return None

    def is_processable(self) -> bool:
        """
        Check if the file is processable based on decoder availability.

        :return: True if processable, False otherwise.
        """
        return self.decoder_func is not None

    # IMAGE PROCESSING AND VISION CALLBACKS
    def image_to_text(self, ai: AiManager, image: Image.Image) -> Optional[VisionSchema]:
        """
        Convert image to RGB if needed, resize, and process with AI vision.
        :param ai: AI manager.
        :param image: PIL Image object.
        :return: VisionSchema result or None if failed.
        """
        if image.mode != "RGB":
            self.logger.info(f"Converted image from '{image.mode}' to 'RGB'")
            image = image.convert("RGB")

        image_possibly_resized = image_resize_safe(image=image, logger=self.logger, verbose=self.ai.cli.VERBOSE_VISION)
        if image_possibly_resized is None:
            self.logger.warning(f"Failed to resize image")
            return None

        image_base64 = image_to_base64(image_possibly_resized)

        vision_result = ai.vision(image_base64)

        if vision_result.is_rejected:
            self.logger.error(f"⚠️ Image rejected: \"{vision_result.rejection_reason}\"")
            return None

        return vision_result

    def image_to_text_ocr(self, ai: AiManager, image: Image.Image) -> Optional[str]:
        """
        Request vision with OCR on the image and format the result.
        :param ai: AI manager.
        :param image: PIL Image object.
        :return: OCR text or None if failed.
        """
        if self.ai.cli.VERBOSE_VISION:
            self.logger.info("Requesting vision feature: OCR")
        ai.request_ocr()
        vision_result = self.image_to_text(ai=ai, image=image)
        if vision_result is not None:
            return AiVisionOCR.format_vision_answer(vision_result=vision_result)
        else:
            return None

    def image_to_text_entity(self, ai: AiManager, image: Image.Image) -> Optional[str]:
        """
        Request vision with entity extraction on the image and format the result.
        :param ai: AI manager.
        :param image: PIL Image object.
        :return: Entity text or None if failed.
        """
        if self.ai.cli.VERBOSE_VISION:
            self.logger.info("Requesting vision feature: Entity Extraction")
        ai.request_entity()
        vision_result = self.image_to_text(ai=ai, image=image)
        if vision_result is not None:
            return AiVisionEntity.format_vision_answer(vision_result=vision_result)
        else:
            return None

    def image_to_text_combined(self, ai: AiManager, image: Image.Image) -> Optional[str]:
        """
        Request vision with OCR and entity extraction on the image, format and join the results.
        :param ai: AI manager.
        :param image: PIL Image object.
        :return: Combined text or None if any part failed.
        """
        if self.ai.cli.VERBOSE_VISION:
            self.logger.info("Requesting vision features: OCR, Entity Extraction")

        ai.request_ocr()
        vision_result_ocr = self.image_to_text(ai=ai, image=image)
        if vision_result_ocr is None:
            return None
        text_ocr = AiVisionOCR.format_vision_answer(vision_result=vision_result_ocr)

        ai.request_entity()
        vision_result_entity = self.image_to_text(ai=ai, image=image)
        if vision_result_entity is None:
            return None
        text_entity = AiVisionEntity.format_vision_answer(vision_result=vision_result_entity)

        # Join with a single space
        return text_ocr + " " + text_entity

    def decode(self, progress_info: ProgressInfo) -> Optional[DocumentContent]:
        """
        Decode the file using the determined decoder function.

        :param progress_info: Progress tracking information
        :return: DocumentContent or None if failed or unsupported
        """
        if self.decoder_func is not None:
            try:
                return self.decoder_func(progress_info)
            except Exception as e:
                self.logger.error(f"Failed to process file: {e}")
                return None

        self.logger.warning(f"Cannot process file")
        return None

    # AI CHUNKING CALLBACK
    # noinspection PyMethodMayBeStatic
    def chunk_callback(self, ai: AiManager, block_of_sentences: List[str]) -> ChunkSchema:
        """
        Callback for chunking a block of sentences using AI.
        :param ai: AI manager.
        :param block_of_sentences: List of sentences to chunk.
        :return: ChunkSchema result.
        """
        chunk_result = ai.chunk(block_of_sentences)

        return chunk_result

    def process(self, progress_manager: ProgressManager, file_progress_key: str) -> bool:
        """
        Process the file through the complete RAG pipeline:
        Phase 1: Document decoding and vision processing (PDF/Binary only)
        Phase 2: Sentence extraction and AI chunking
        Phase 3: Reference range analysis and setup
        Phase 4: Parallel embedding and vector point creation

        :param progress_manager: Progress manager for progress reporting.
        :param file_progress_key: File progress key for progress tracking.
        :return: True if successful, False otherwise.
        """

        # PHASE 1: Document Decoding and Image Processing
        vision_progress_key = None
        if is_pdf_document(self.file_path) or is_binary_document(self.file_path):
            # Use generic interface - create child task under file
            vision_progress_key = progress_manager.start_task("Image Processing", parent=file_progress_key, weight=0.33)
            progress_manager.activate_task(vision_progress_key)

        # Call the loader function assigned to this file data.
        # NOTE: DocumentContent is an array of text lines, mapped to page or line numbers.
        # Create ProgressInfo for clean parameter passing
        if vision_progress_key:
            vision_progress_info = progress_manager.create_progress_info(vision_progress_key)
        else:
            # For text-only files, decode() reports against file-level progress
            vision_progress_info = progress_manager.create_progress_info(file_progress_key)
        doc_content: Optional[DocumentContent] = self.decode(vision_progress_info)

        # Complete image processing phase if it was created
        if vision_progress_key is not None:
            progress_manager.complete_task(vision_progress_key)

        # Decoder may fail, e.g. on I/O error, exhausted AI attempts, …
        if doc_content is None:
            self.logger.warning(f"Failed to decode document")
            return False

        # PHASE 2: Sentence Extraction and AI Chunking
        doc_content.strip_lines()

        # Use preprocessing and NLP (spaCy) to split text into sentences, keeping track of references.
        if self.ai.cli.VERBOSE_CHUNK:
            self.logger.info(f"Extracting sentences across ({len(doc_content.lines)}) lines")
        sentences_with_reference_ranges = get_sentences_with_reference_ranges(doc_content)

        # Create chunking phase - use generic interface
        has_vision = is_pdf_document(self.file_path) or is_binary_document(self.file_path)
        chunking_weight = 0.34 if has_vision else 0.50
        chunking_progress_key = progress_manager.start_task("Chunking", parent=file_progress_key, weight=chunking_weight)
        progress_manager.activate_task(chunking_progress_key)

        # Group sentences into chunks, keeping track of references.
        if self.ai.cli.VERBOSE_CHUNK:
            self.logger.info(f"Extracting chunks across ({len(sentences_with_reference_ranges)}) sentences")
        chunks = get_chunks_with_reference_ranges(
            ai_factory=self.ai_factory,
            sentences_with_references=sentences_with_reference_ranges,
            chunk_callback=self.chunk_callback,
            chunk_lines_block=self.chunk_lines_block,
            file_path=self.file_path,
            progress_info=progress_manager.create_progress_info(chunking_progress_key),
            logger=self.logger,
            verbose=self.ai.cli.VERBOSE_CHUNK,
        )

        # Complete chunking phase
        progress_manager.complete_task(chunking_progress_key)

        # PHASE 3: Reference Range Analysis and Point Creation Setup
        is_page_based = doc_content.pages_per_line is not None

        if is_page_based:
            max_page = max(doc_content.pages_per_line) if doc_content.pages_per_line else 0
            reference_total_info = f"{max_page}"
        else:
            max_line = max(doc_content.lines_per_line) if doc_content.lines_per_line else 0
            reference_total_info = f"{max_line}"

        # Create embedding phase - use generic interface
        embedding_weight = 0.33 if has_vision else 0.50
        embedding_progress_key = progress_manager.start_task(
            "Embedding", parent=file_progress_key, weight=embedding_weight, total=len(chunks)
        )
        progress_manager.activate_task(embedding_progress_key)

        # PHASE 4: Parallel Embedding and Vector Point Creation
        # Process chunks in parallel for embedding
        embedding_results = self.chunk_processor.process_chunks_parallel(
            chunks=chunks,
            verbose=self.ai.cli.VERBOSE_CHUNK,
            progress_info=progress_manager.create_progress_info(embedding_progress_key)
        )

        # Process results and create points
        for chunk_index, (chunk, vector) in enumerate(embedding_results):
            if vector is None:
                self.logger.warning(f"Failed to embed chunk ({chunk_index + 1}) / ({len(chunks)})")
                continue

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

            self.points.append(point)

        # Complete embedding phase
        progress_manager.complete_task(embedding_progress_key)

        return True
