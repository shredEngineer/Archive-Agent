# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
import io
from dataclasses import dataclass, field
from typing import Optional, List, Set, Any, Dict, Tuple

# noinspection PyPackageRequirements
import fitz

from PIL import Image

from archive_agent.config.DecoderSettings import OcrStrategy, DecoderSettings
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.format import format_file
from archive_agent.data.loader.image import ImageToTextCallback
from archive_agent.util.text_util import splitlines_exact
from archive_agent.util.PageTextBuilder import PageTextBuilder


TINY_IMAGE_WIDTH_THRESHOLD: int = 32
TINY_IMAGE_HEIGHT_THRESHOLD: int = 32

OCR_STRATEGY_STRICT_PAGE_DPI: int = 300


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
        logger: Logger,
        file_path: str,
        image_to_text_callback_page: Optional[ImageToTextCallback],
        image_to_text_callback_image: Optional[ImageToTextCallback],
        decoder_settings: DecoderSettings,
) -> Optional[DocumentContent]:
    """
    Load PDF document.
    :param logger: Logger.
    :param file_path: File path.
    :param image_to_text_callback_page: Optional image-to-text callback for pages (`strict` OCR strategy).
    :param image_to_text_callback_image: Optional image-to-text callback for images (`relaxed` OCR strategy).
    :param decoder_settings: Decoder settings.
    :return: Document content if successful, None otherwise.
    """
    doc: fitz.Document = fitz.open(file_path)

    page_contents = get_pdf_page_contents(
        logger=logger,
        doc=doc,
        decoder_settings=decoder_settings,
    )

    image_texts_per_page = None

    if image_to_text_callback_page is None or image_to_text_callback_image is None:
        logger.warning(f"Image vision is DISABLED in your current configuration")
    else:
        image_texts_per_page = extract_image_texts_per_page(
            logger=logger,
            file_path=file_path,
            page_contents=page_contents,
            image_to_text_callback_page=image_to_text_callback_page,
            image_to_text_callback_image=image_to_text_callback_image,
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
        logger: Logger,
        file_path: str,
        page_contents: List[PdfPageContent],
        image_to_text_callback_page: ImageToTextCallback,
        image_to_text_callback_image: ImageToTextCallback,
) -> List[List[str]]:
    """
    Extract text from images per page.
    :param logger: Logger.
    :param file_path: File path (used for logging only).
    :param page_contents: PDF page contents.
    :param image_to_text_callback_page: Optional image-to-text callback for pages (`strict` OCR strategy).
    :param image_to_text_callback_image: Optional image-to-text callback for images (`relaxed` OCR strategy).
    :return: List of text results per page (one list of strings per page).
    """
    image_texts_per_page: List[List[str]] = []

    for page_index, content in enumerate(page_contents):
        image_texts: List[str] = []

        for image_index, image_bytes in enumerate(content.layout_image_bytes):
            log_header = (
                f"Processing image ({image_index + 1}) "
                f"on page ({page_index + 1}) / ({len(page_contents)}) "
                f"of {format_file(file_path)}"
            )

            try:
                # noinspection PyTypeChecker
                with Image.open(io.BytesIO(image_bytes)) as image:
                    if image.width <= TINY_IMAGE_WIDTH_THRESHOLD or image.height <= TINY_IMAGE_HEIGHT_THRESHOLD:
                        logger.warning(f"{log_header}: Ignored because it's tiny ({image.width} × {image.height} px)")
                        continue

                    logger.info(f"{log_header}: Converting to text")

                    if content.ocr_strategy == OcrStrategy.STRICT:
                        image_text = image_to_text_callback_page(image)
                    else:
                        image_text = image_to_text_callback_image(image)

                    if image_text is None:
                        if content.ocr_strategy == OcrStrategy.STRICT:
                            image_texts.append(f"[Unprocessable page]")
                        else:
                            image_texts.append(f"[Unprocessable image]")
                        logger.warning(f"{log_header}: Unprocessable image")
                        continue

                    assert len(splitlines_exact(image_text)) == 1, f"Text from image must be single line:\n'{image_text}'"

                    if content.ocr_strategy == OcrStrategy.RELAXED:
                        # Add brackets around image text for `relaxed` OCR strategy (separate from "actual" text)
                        image_text = f"[{image_text}]"

                    image_texts.append(image_text)

            except Exception as e:
                logger.warning(f"{log_header}: Failed to extract text: {e}")

        image_texts_per_page.append(image_texts)

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
        doc: fitz.Document,
        decoder_settings: DecoderSettings,
) -> List[PdfPageContent]:
    """
    Get PDF page contents.
    :param logger: Logger.
    :param doc: PDF document.
    :param decoder_settings: Decoder settings.
    :return: PDF page contents.
    """
    page_contents: List[PdfPageContent] = []
    pages: List[Any] = [page for page in doc]
    for page_index, page in enumerate(pages):

        logger.info(f"Analyzing PDF page ({page_index + 1}) / ({len(pages)}):")
        page_content: PdfPageContent = get_pdf_page_content(page)

        # Resolve `auto` OCR strategy
        if decoder_settings.ocr_strategy == OcrStrategy.AUTO:
            if len(page_content.text) >= decoder_settings.ocr_auto_threshold:
                page_content.ocr_strategy = OcrStrategy.RELAXED
                logger.info(f"- OCR strategy: 'auto' resolved to 'relaxed'")
            else:
                page_content.ocr_strategy = OcrStrategy.STRICT
                logger.info(f"- OCR strategy: 'auto' resolved to 'strict'")
        else:
            page_content.ocr_strategy = decoder_settings.ocr_strategy
            logger.info(f"- OCR strategy: '{page_content.ocr_strategy.value}'")

        if page_content.ocr_strategy == OcrStrategy.STRICT:
            # Replace page content with only one full-page image.
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

    return page_contents
