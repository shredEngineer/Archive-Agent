#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from pathlib import Path
from typing import List, Optional, Type

import typer
from PIL import Image

from archive_agent.ai.AiManager import AiManager
from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.ai.vision.AiVisionOCR import AiVisionOCR
from archive_agent.ai_provider.AiProvider import AiProvider
from archive_agent.ai_provider.AiProviderParams import AiProviderParams
from archive_agent.ai_provider.ai_provider_registry import ai_provider_registry
from archive_agent.core.CacheManager import CacheManager
from archive_agent.core.CliManager import CliManager
from archive_agent.core.ProgressManager import ProgressManager, ProgressInfo
from archive_agent.config.ConfigManager import ConfigManager
from archive_agent.data.loader.PdfDocument import PdfDocument, PdfPage
from archive_agent.data.loader.backend.pdf_pymupdf import create_pdf_document
from archive_agent.data.processor.VisionProcessor import VisionProcessor, VisionRequest
from archive_agent.profile.ProfileManager import ProfileManager
from archive_agent.util.image_util import image_resize_safe, image_to_base64


DEFAULT_DPI: int = 150


class StandaloneOcr:
    """
    Standalone STRICT OCR processor for PDF files.

    Converts each PDF page to a full-page image and processes it through
    AI vision OCR, producing a Markdown file with the extracted text.

    This processor uses a lightweight initialization that does NOT require
    a running Qdrant database or any watchlist/commit infrastructure.
    """

    def __init__(
            self,
            cli: CliManager,
            progress_manager: ProgressManager,
            ai_factory: AiManagerFactory,
            verbose: bool,
            max_workers_vision: int,
            dpi: int,
    ):
        """
        Initialize standalone OCR processor.
        :param cli: CLI manager.
        :param progress_manager: Progress manager.
        :param ai_factory: AI manager factory.
        :param verbose: Enable verbose output.
        :param max_workers_vision: Max. workers for vision processing.
        :param dpi: DPI for full-page rendering.
        """
        self.cli = cli
        self.progress_manager = progress_manager
        self.ai_factory = ai_factory
        self.verbose = verbose
        self.max_workers_vision = max_workers_vision
        self.dpi = dpi
        self.logger = cli.logger

    @staticmethod
    def create_from_profile(
            verbose: bool,
            nocache: bool,
            dpi: int,
    ) -> "StandaloneOcr":
        """
        Lightweight factory that reads profile config without initializing Qdrant.

        Sets up only the minimal components needed for vision OCR:
        CliManager, ProgressManager, ProfileManager, ConfigManager,
        CacheManager, and AiManagerFactory.

        :param verbose: Enable verbose output.
        :param nocache: Invalidate AI cache.
        :param dpi: DPI for full-page rendering.
        :return: Configured StandaloneOcr instance.
        """
        settings_path = Path.home() / ".archive-agent-settings"

        cli = CliManager(verbose=verbose)
        progress_manager = ProgressManager(cli.console)

        profile_manager = ProfileManager(
            cli=cli,
            settings_path=settings_path,
            profile_name=None,
        )

        config = ConfigManager(
            cli=cli,
            settings_path=settings_path,
            profile_name=profile_manager.get_profile_name(),
        )

        ai_cache = CacheManager(
            cli=cli,
            cache_path=settings_path / profile_manager.get_profile_name() / "ai_cache",
            invalidate_cache=nocache,
            verbose=verbose,
        )

        ai_provider_name = config.data[config.AI_PROVIDER]
        if ai_provider_name not in ai_provider_registry:
            raise ValueError(
                f"Invalid AI provider: '{ai_provider_name}' "
                f"(must be one of {list(ai_provider_registry.keys())})"
            )
        ai_provider_class: Type[AiProvider] = ai_provider_registry[ai_provider_name]["class"]

        ai_provider_params = AiProviderParams(
            model_chunk=config.data[config.AI_MODEL_CHUNK],
            model_embed=config.data[config.AI_MODEL_EMBED],
            model_rerank=config.data[config.AI_MODEL_RERANK],
            model_query=config.data[config.AI_MODEL_QUERY],
            model_vision=config.data[config.AI_MODEL_VISION],
            temperature_query=config.data[config.AI_TEMPERATURE_QUERY],
        )

        if not ai_provider_params.model_vision:
            cli.logger.error("No vision model configured. Set 'ai_model_vision' in your profile config.")
            raise typer.Exit(code=1)

        ai_factory = AiManagerFactory(
            cli=cli,
            chunk_lines_block=config.data[config.CHUNK_LINES_BLOCK],
            chunk_words_target=config.data[config.CHUNK_WORDS_TARGET],
            ai_provider_class=ai_provider_class,
            ai_provider_params=ai_provider_params,
            ai_cache=ai_cache,
            invalidate_cache=nocache,
            server_url=config.data[config.AI_SERVER_URL],
        )

        max_workers_vision = config.data[config.MAX_WORKERS_VISION]

        cli.logger.info(f"Using AI provider: '{ai_provider_name}' @ {config.data[config.AI_SERVER_URL]}")
        cli.logger.info(f"Using vision model: '{ai_provider_params.model_vision}'")

        return StandaloneOcr(
            cli=cli,
            progress_manager=progress_manager,
            ai_factory=ai_factory,
            verbose=verbose,
            max_workers_vision=max_workers_vision,
            dpi=dpi,
        )

    def process(self, pdf_path: str) -> Path:
        """
        Process a PDF file with STRICT OCR and write the result as Markdown.
        :param pdf_path: Path to the PDF file.
        :return: Path to the output Markdown file.
        """
        resolved_path = Path(pdf_path).expanduser().resolve()

        if not resolved_path.exists():
            self.logger.error(f"File not found: {resolved_path}")
            raise typer.Exit(code=1)

        if not resolved_path.suffix.lower() == ".pdf":
            self.logger.error(f"Not a PDF file: {resolved_path}")
            raise typer.Exit(code=1)

        output_path = get_output_path(str(resolved_path))

        self.logger.info(f"Processing: {resolved_path}")
        self.logger.info(f"DPI: {self.dpi}")

        page_texts = self._ocr_all_pages(str(resolved_path))

        markdown = build_markdown(page_texts)

        output_path.write_text(markdown, encoding="utf-8")
        self.logger.info(f"Written: {output_path}")

        return output_path

    def _ocr_all_pages(self, file_path: str) -> List[Optional[str]]:
        """
        Render all PDF pages as images and run STRICT OCR on each.
        :param file_path: Path to the PDF file.
        :return: List of OCR text per page (None for failed pages).
        """
        doc: PdfDocument = create_pdf_document(file_path)
        pages: List[PdfPage] = list(doc)

        if not pages:
            self.logger.warning("PDF has no pages")
            return []

        self.logger.info(f"Pages: {len(pages)}")

        # Create root progress task
        root_key = self.progress_manager.start_task(
            "Standalone OCR", total=len(pages)
        )
        progress_info = self.progress_manager.create_progress_info(root_key)

        # Build vision requests for all pages
        vision_requests: List[VisionRequest] = []
        for page_index, page in enumerate(pages):
            if self.verbose:
                self.logger.info(f"Rendering page ({page_index + 1}) / ({len(pages)}) at {self.dpi} DPI")

            image_bytes = page.get_full_page_pixmap(dpi=self.dpi)

            vision_request = VisionRequest(
                image_data=image_bytes,
                callback=_ocr_callback,
                formatter=lambda result: "[Unprocessable page]" if result is None else result,
                log_header=f"OCR page ({page_index + 1}) / ({len(pages)})",
                image_index=page_index,
                page_index=page_index,
            )
            vision_requests.append(vision_request)

        if not vision_requests:
            return []

        # Process all pages in parallel via VisionProcessor
        logger = self.cli.get_prefixed_logger(prefix="OCR")
        vision_processor = VisionProcessor(
            ai_factory=self.ai_factory,
            logger=logger,
            verbose=self.verbose,
            file_path=file_path,
            max_workers=self.max_workers_vision,
        )

        results = vision_processor.process_vision_requests_parallel(
            vision_requests, progress_info
        )

        self.progress_manager.complete_task(root_key)

        # Map results: "[Unprocessable page]" -> None, otherwise text
        page_texts: List[Optional[str]] = []
        for result in results:
            if result == "[Unprocessable page]":
                page_texts.append(None)
            else:
                page_texts.append(result)

        return page_texts


def _ocr_callback(
        ai: AiManager,
        image: Image.Image,
        progress_info: ProgressInfo,
) -> Optional[str]:
    """
    Vision OCR callback for standalone processing.
    :param ai: AI manager (dedicated worker instance).
    :param image: PIL Image to OCR.
    :param progress_info: Progress tracking.
    :return: OCR text or None if failed.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    image_possibly_resized = image_resize_safe(
        image=image,
        logger=ai.cli.logger,
        verbose=ai.cli.VERBOSE_VISION,
    )
    if image_possibly_resized is None:
        return None

    image_base64 = image_to_base64(image_possibly_resized)

    ai.request_ocr()
    vision_result = ai.vision(image_base64)

    progress_info.progress_manager.update_task(progress_info.parent_key, advance=1)

    if vision_result.is_rejected:
        ai.cli.logger.error(f"Image rejected: \"{vision_result.rejection_reason}\"")
        return None

    return AiVisionOCR.format_vision_answer(vision_result=vision_result)


def get_output_path(pdf_path: str) -> Path:
    """
    Get the output Markdown path for a given PDF path.
    Replaces the .pdf extension with .md.
    :param pdf_path: Path to the PDF file.
    :return: Path to the output Markdown file.
    """
    path = Path(pdf_path)
    return path.with_suffix(".md")


def sanitize_unicode(text: str) -> str:
    """
    Replace problematic Unicode whitespace characters with regular spaces.
    AI vision models sometimes produce em spaces (U+2003) and other Unicode
    whitespace that does not render correctly in many editors.
    :param text: Input text.
    :return: Sanitized text.
    """
    # Unicode whitespace characters that should be normalized to regular spaces
    unicode_spaces = {
        "\u2003",  # Em Space
        "\u2002",  # En Space
        "\u2004",  # Three-Per-Em Space
        "\u2005",  # Four-Per-Em Space
        "\u2006",  # Six-Per-Em Space
        "\u2007",  # Figure Space
        "\u2008",  # Punctuation Space
        "\u2009",  # Thin Space
        "\u200A",  # Hair Space
        "\u00A0",  # Non-Breaking Space
        "\u202F",  # Narrow No-Break Space
    }
    for char in unicode_spaces:
        text = text.replace(char, " ")
    return text


def build_markdown(page_texts: List[Optional[str]]) -> str:
    """
    Assemble page OCR results into a Markdown document.

    Each page gets a heading (``# Page N``) followed by its OCR text.
    Failed pages are marked with ``*[Unprocessable page]*``.

    :param page_texts: List of OCR text per page (None for failed pages).
    :return: Markdown string.
    """
    if not page_texts:
        return ""

    parts: List[str] = []

    for page_index, text in enumerate(page_texts):
        page_number = page_index + 1
        parts.append(f"# Page {page_number}")
        parts.append("")

        if text is not None:
            parts.append(sanitize_unicode(text))
        else:
            parts.append("*[Unprocessable page]*")

        parts.append("")

    return "\n".join(parts)
