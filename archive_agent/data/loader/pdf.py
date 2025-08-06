# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
import io
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Set, Any, Dict, Tuple

from rich.progress import Progress

# noinspection PyPackageRequirements
import fitz

from PIL import Image

from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.config.DecoderSettings import OcrStrategy, DecoderSettings
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.data.loader.image import ImageToTextCallback
from archive_agent.util.text_util import splitlines_exact
from archive_agent.util.PageTextBuilder import PageTextBuilder
from archive_agent.data.processor.VisionProcessor import VisionProcessor, VisionRequest


TINY_IMAGE_WIDTH_THRESHOLD: int = 32
TINY_IMAGE_HEIGHT_THRESHOLD: int = 32

OCR_STRATEGY_STRICT_PAGE_DPI: int = 300

# Module-level lock for PyMuPDF operations to prevent threading issues
# PyMuPDF does not support multithreading - this ensures only one PDF analyzing phase runs at a time
_PDF_ANALYZING_LOCK = threading.Lock()


LayoutBlock = Dict[str, Any]
ImageObject = Tuple[Any, ...]


@dataclass
class PdfPageContent:
    """
    PDF page content.
    """
    text: str = ""

    layout_image_bytes: List[bytes] = field(default_factory=list)

    text_blocks: List[LayoutBlock] = field(default_factory=list)
    image_blocks: List[LayoutBlock] = field(default_factory=list)
    vector_blocks: List[LayoutBlock] = field(default_factory=list)
    other_blocks: List[LayoutBlock] = field(default_factory=list)
    image_objects: List[ImageObject] = field(default_factory=list)

    ocr_strategy: OcrStrategy = field(default=OcrStrategy.AUTO)


def is_pdf_document(file_path: str) -> bool:
    """
    Checks if the given file path has a valid PDF document extension.
    :param file_path: File path.
    :return: True if the file path has a valid PDF document extension, False otherwise.
    """
    extensions: Set[str] = {".pdf"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_pdf_document(
        ai_factory: AiManagerFactory,
        logger: Logger,
        verbose: bool,
        file_path: str,
        max_workers_vision: int,
        image_to_text_callback_page: Optional[ImageToTextCallback],
        image_to_text_callback_image: Optional[ImageToTextCallback],
        decoder_settings: DecoderSettings,
        progress: Optional[Progress] = None,
        vision_task_id: Optional[Any] = None,
) -> Optional[DocumentContent]:
    """
    Load PDF document.
    :param ai_factory: AI manager factory.
    :param logger: Logger.
    :param verbose: Enable verbose output.
    :param file_path: File path.
    :param max_workers_vision: Max. workers for vision.
    :param image_to_text_callback_page: Optional image-to-text callback for pages (`strict` OCR strategy).
    :param image_to_text_callback_image: Optional image-to-text callback for images (`relaxed` OCR strategy).
    :param decoder_settings: DecoderSettings.
    :param progress: A rich.progress.Progress object for progress reporting.
    :param vision_task_id: The vision task ID for progress reporting.
    :return: Document content if successful, None otherwise.
    """
    doc: fitz.Document = fitz.open(file_path)

    # Use module-level lock to serialize PyMuPDF analyzing operations across all threads
    # This allows vision/chunking/embedding phases to run in parallel while
    # ensuring only one PDF analyzing phase executes at a time
    with _PDF_ANALYZING_LOCK:
        if verbose:
            logger.info("Acquired PDF analyzing lock - starting page analysis")

        page_contents = get_pdf_page_contents(
            logger=logger,
            verbose=verbose,
            doc=doc,
            decoder_settings=decoder_settings,
            progress=progress,
        )

        if verbose:
            logger.info("PDF analyzing complete - releasing lock")

    image_texts_per_page = None

    if image_to_text_callback_page is None or image_to_text_callback_image is None:
        logger.warning(f"Image vision is DISABLED in your current configuration")
    else:
        image_texts_per_page = extract_image_texts_per_page(
            ai_factory=ai_factory,
            logger=logger,
            verbose=verbose,
            file_path=file_path,
            max_workers_vision=max_workers_vision,
            page_contents=page_contents,
            image_to_text_callback_page=image_to_text_callback_page,
            image_to_text_callback_image=image_to_text_callback_image,
            progress=progress,
            vision_task_id=vision_task_id,
        )

    return build_document_text_from_pages(page_contents, image_texts_per_page)


def build_document_text_from_pages(
        page_contents: List[PdfPageContent],
        image_texts_per_page: Optional[List[List[str]]] = None
) -> Optional[DocumentContent]:
    """
    Build PDF document text by combining layout text and image text, with per-line page mapping.
    This function *guarantees* that every line in `text` has a matching entry in `pages_per_line`.
    :param page_contents: Page contents.
    :param image_texts_per_page: Image texts per page.
    :return: Document content if successful, None otherwise.
    """
    if image_texts_per_page is not None:
        assert len(page_contents) == len(image_texts_per_page)

    builder = PageTextBuilder()

    for page_index, page_content in enumerate(page_contents):
        page_number = page_index + 1

        # Append image text
        if image_texts_per_page is not None:

            for image_text in image_texts_per_page[page_index]:

                assert len(splitlines_exact(image_text)) == 1, f"Text from image must be single line:\n'{image_text}'"

                builder.push("", page_number)
                builder.push(image_text, page_number)
                builder.push("", page_number)

        # Append text
        page_lines = splitlines_exact(page_content.text)
        for line in page_lines:
            builder.push(line, page_number)

        # Append empty line at end of page
        builder.push()

    return builder.getDocumentContent()


# ### Automatic OCR stuff ### #


def extract_image_texts_per_page(
        ai_factory: AiManagerFactory,
        logger: Logger,
        verbose: bool,
        file_path: str,
        max_workers_vision: int,
        page_contents: List[PdfPageContent],
        image_to_text_callback_page: ImageToTextCallback,
        image_to_text_callback_image: ImageToTextCallback,
        progress: Optional[Progress] = None,
        vision_task_id: Optional[Any] = None,
) -> List[List[str]]:
    """
    Extract text from images per page.
    :param ai_factory: AI manager factory.
    :param logger: Logger.
    :param verbose: Enable verbose output.
    :param file_path: File path (used for logging only).
    :param max_workers_vision: Max. workers for vision.
    :param page_contents: PDF page contents.
    :param image_to_text_callback_page: Optional image-to-text callback for pages (`strict` OCR strategy).
    :param image_to_text_callback_image: Optional image-to-text callback for images (`relaxed` OCR strategy).
    :param progress: A rich.progress.Progress object for progress reporting.
    :param vision_task_id: The vision task ID for progress reporting.
    :return: List of text results per page (one list of strings per page).
    """
    # Create VisionProcessor for batch processing
    vision_processor = VisionProcessor(ai_factory, logger, verbose, file_path, max_workers_vision)
    vision_requests = []

    # Collect all vision requests across all pages
    for page_index, content in enumerate(page_contents):
        for image_index, image_bytes in enumerate(content.layout_image_bytes):
            log_header = f"Image ({image_index + 1}) on page ({page_index + 1}) / ({len(page_contents)}) "

            try:
                # noinspection PyTypeChecker
                with Image.open(io.BytesIO(image_bytes)) as image:
                    if image.width <= TINY_IMAGE_WIDTH_THRESHOLD or image.height <= TINY_IMAGE_HEIGHT_THRESHOLD:
                        logger.warning(f"{log_header}: Ignored because it's tiny ({image.width} × {image.height} px)")
                        continue

                    if verbose:
                        logger.info(f"{log_header}: Queueing")

                    # Choose callback based on OCR strategy (preserve original logic)
                    if content.ocr_strategy == OcrStrategy.STRICT:
                        callback = image_to_text_callback_page
                        formatter = lambda result: "[Unprocessable page]" if result is None else result
                    else:
                        callback = image_to_text_callback_image
                        formatter = lambda result: "[Unprocessable image]" if result is None else f"[{result}]"

                    vision_request = VisionRequest(
                        image_data=image_bytes,
                        callback=callback,
                        formatter=formatter,
                        log_header=f"{log_header}: Converting to text",
                        image_index=image_index,
                        page_index=page_index
                    )
                    vision_requests.append(vision_request)

            except Exception as e:
                logger.error(f"{log_header}: Failed to extract text: {e}")

    image_texts_per_page: List[List[str]] = [[] for _ in range(len(page_contents))]

    if not vision_requests:
        return image_texts_per_page

    # Update progress total now that we know the number of vision requests
    if progress and vision_task_id:
        progress.update(vision_task_id, total=len(vision_requests))

    # Process all requests in parallel
    vision_results = vision_processor.process_vision_requests_parallel(vision_requests, progress, vision_task_id)

    # Reassemble results into per-page structure
    for request_index, formatted_result in enumerate(vision_results):
        request = vision_requests[request_index]
        page_index = request.page_index

        image_texts_per_page[page_index].append(formatted_result)

    return image_texts_per_page


def get_pdf_page_content(page: fitz.Page) -> PdfPageContent:
    """
    Get PDF page content.
    :param page: PDF page.
    :return: PDF page content.
    """
    text: str = page.get_text("text").strip()  # type: ignore

    image_objects: List[ImageObject] = page.get_images(full=True)

    blocks: List[LayoutBlock] = page.get_text("dict")["blocks"]  # type: ignore

    text_blocks: List[LayoutBlock] = []
    image_blocks: List[LayoutBlock] = []
    vector_blocks: List[LayoutBlock] = []
    other_blocks: List[LayoutBlock] = []
    layout_image_bytes: List[bytes] = []

    for block in blocks:
        block_type = block.get("type", "other")
        if block_type == 0:
            text_blocks.append(block)
        elif block_type == 1:
            image_blocks.append(block)
            img = block.get("image")
            if img:
                layout_image_bytes.append(img)
        elif block_type == 2:
            vector_blocks.append(block)
        else:
            other_blocks.append(block)

    return PdfPageContent(
        text=text,
        layout_image_bytes=layout_image_bytes,
        text_blocks=text_blocks,
        image_blocks=image_blocks,
        vector_blocks=vector_blocks,
        other_blocks=other_blocks,
        image_objects=image_objects,
    )


def get_pdf_page_contents(
        logger: Logger,
        verbose: bool,
        doc: fitz.Document,
        decoder_settings: DecoderSettings,
        progress: Optional[Progress] = None,
) -> List[PdfPageContent]:
    """
    Get PDF page contents.
    :param logger: Logger.
    :param verbose: Enable verbose output.
    :param doc: PDF document.
    :param decoder_settings: Decoder settings.
    :param progress: A rich.progress.Progress object for progress reporting.
    :return: PDF page contents.
    """
    page_contents: List[PdfPageContent] = []
    pages: List[Any] = [page for page in doc]

    # Create PDF analyzing sub-task if progress tracking is enabled
    analyzing_task_id = None
    if progress:
        analyzing_task_id = progress.add_task("[cyan]PDF Analyzing[/cyan]", total=len(pages))

    for page_index, page in enumerate(pages):

        if verbose:
            logger.info(f"Analyzing PDF page ({page_index + 1}) / ({len(pages)}):")
        page_content: PdfPageContent = get_pdf_page_content(page)

        # Resolve `auto` OCR strategy
        if decoder_settings.ocr_strategy == OcrStrategy.AUTO:
            if len(page_content.text) >= decoder_settings.ocr_auto_threshold:
                page_content.ocr_strategy = OcrStrategy.RELAXED
                if verbose:
                    logger.info(f"- OCR strategy: 'auto' resolved to 'relaxed'")
            else:
                page_content.ocr_strategy = OcrStrategy.STRICT
                if verbose:
                    logger.info(f"- OCR strategy: 'auto' resolved to 'strict'")
        else:
            page_content.ocr_strategy = decoder_settings.ocr_strategy
            if verbose:
                logger.info(f"- OCR strategy: '{page_content.ocr_strategy.value}'")

        if page_content.ocr_strategy == OcrStrategy.STRICT:
            # Replace page content with only one full-page image.
            if verbose:
                logger.info(f"- IGNORING ({len(page_content.image_blocks)}) image(s)")
                logger.info(f"- IGNORING ({len(page_content.text)}) character(s) in ({len(page_content.text_blocks)}) text block(s)")
                logger.info(f"- Decoding full-page image (rendered at {OCR_STRATEGY_STRICT_PAGE_DPI} DPI) ")
            page_content = PdfPageContent(
                text="",
                layout_image_bytes=[page.get_pixmap(dpi=OCR_STRATEGY_STRICT_PAGE_DPI).tobytes()],
                ocr_strategy=OcrStrategy.STRICT,
            )

        elif page_content.ocr_strategy == OcrStrategy.RELAXED:
            # Keep page content as-is.
            if verbose:
                logger.info(f"- Decoding ({len(page_content.image_blocks)}) image(s)")
                logger.info(f"- Decoding ({len(page_content.text)}) character(s) in ({len(page_content.text_blocks)}) text block(s)")

            num_background_images: int = len(page_content.image_objects) - len(page_content.image_blocks)
            if num_background_images > 0:
                logger.warning(f"- IGNORING ({num_background_images}) background image(s)")

            if page_content.vector_blocks:
                logger.warning(f"- IGNORING ({len(page_content.vector_blocks)}) vector diagram(s)")

        else:
            raise ValueError(f"Invalid or unhandled OCR strategy: '{page_content.ocr_strategy.value}'")

        assert page_content.ocr_strategy != OcrStrategy.AUTO, "BUG DETECTED: Unresolved `auto` OCR strategy"  # should never happen

        page_contents.append(page_content)

        # Update analyzing progress
        if progress and analyzing_task_id is not None:
            progress.update(analyzing_task_id, advance=1)

    # Clean up analyzing task and update main file progress
    if progress and analyzing_task_id is not None:
        progress.remove_task(analyzing_task_id)

    return page_contents
