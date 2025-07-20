# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import logging
import io
from dataclasses import dataclass, field
from typing import Optional, List, Set, Any, Dict, Tuple

# noinspection PyPackageRequirements
import fitz

from PIL import Image

from archive_agent.config.DecoderSettings import OcrStrategy, DecoderSettings
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.format import format_file
from archive_agent.loader.image import ImageToTextCallback

logger = logging.getLogger(__name__)


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


def is_pdf_document(file_path: str) -> bool:
    """
    Checks if the given file path has a valid PDF document extension.
    :param file_path: File path.
    :return: True if the file path has a valid PDF document extension, False otherwise.
    """
    extensions: Set[str] = {".pdf"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_pdf_document(
        file_path: str,
        image_to_text_callback: Optional[ImageToTextCallback],
        decoder_settings: DecoderSettings,
) -> Optional[DocumentContent]:
    """
    Load PDF document.
    :param file_path: File path.
    :param image_to_text_callback: Optional image-to-text callback.
    :param decoder_settings: Decoder settings.
    :return: Document content if successful, None otherwise.
    """
    doc: fitz.Document = fitz.open(file_path)

    page_contents = get_pdf_page_contents(
        doc=doc,
        decoder_settings=decoder_settings,
    )

    image_texts_per_page = None

    if image_to_text_callback is None:
        logger.warning(f"Image vision is DISABLED in your current configuration")
    else:
        image_texts_per_page = extract_text_from_images_per_page(
            file_path,
            page_contents,
            image_to_text_callback,
        )

    return build_document_text_from_pages(page_contents, image_texts_per_page)


def build_document_text_from_pages(
        page_contents: List[PdfPageContent],
        image_texts_per_page: Optional[List[List[str]]] = None
) -> Optional[DocumentContent]:
    """
    Build PDF document text by combining layout text and image text, with per-line page mapping.
    This function *guarantees* that every line in `text` has a matching entry in `pages_per_line`.
    """
    if image_texts_per_page is not None:
        assert len(page_contents) == len(image_texts_per_page)

    all_lines: List[str] = []
    pages_per_line: List[int] = []

    for page_idx, content in enumerate(page_contents):
        page_number = page_idx + 1

        # Image text lines (if any)
        if image_texts_per_page is not None:
            for img_text in image_texts_per_page[page_idx]:
                img_lines = img_text.splitlines() if img_text else []
                for line in img_lines:
                    all_lines.append(line)
                    pages_per_line.append(page_number)
                # Optionally: Add a blank line after image block? (decide: if yes, then also pages_per_line)
                if img_lines:
                    all_lines.append("")
                    pages_per_line.append(page_number)

        # Main text lines
        page_lines = content.text.splitlines()
        for line in page_lines:
            all_lines.append(line)
            pages_per_line.append(page_number)

        # Blank line to separate pages (except after last page)
        if page_idx < len(page_contents) - 1:
            all_lines.append("")
            pages_per_line.append(page_number)

    if not all_lines:
        return None

    if all_lines and all_lines[-1] == "":
        all_lines.pop()
        pages_per_line.pop()

    full_text = "\n".join(all_lines)

    assert len(full_text.splitlines()) == len(pages_per_line), \
        f"Mismatch: pages_per_line[{len(pages_per_line)}] pages VS full_text[{len(full_text.splitlines())}] lines"

    return DocumentContent(text=full_text, pages_per_line=pages_per_line)


# ### Automatic OCR stuff ### #


def extract_text_from_images_per_page(
        file_path: str,
        page_contents: List[PdfPageContent],
        image_to_text_callback: ImageToTextCallback,
) -> List[List[str]]:
    """
    Extract text from images per page.
    :param file_path: File path (used for logging only).
    :param page_contents: PDF page contents.
    :param image_to_text_callback: Image-to-text callback.
    :return: List of text results per page (one list of strings per page).
    """
    all_image_texts: List[List[str]] = []

    for index, content in enumerate(page_contents):
        page_image_texts: List[str] = []
        logger.info(f"Processing {format_file(file_path)}")

        for i, img_bytes in enumerate(content.layout_image_bytes):
            try:
                # noinspection PyTypeChecker
                with Image.open(io.BytesIO(img_bytes)) as img:
                    if img.width <= TINY_IMAGE_WIDTH_THRESHOLD or img.height <= TINY_IMAGE_HEIGHT_THRESHOLD:
                        logger.warning(
                            f"Image ({i + 1}) on page ({index + 1}) / ({len(page_contents)}): "
                            f"Ignored because it's tiny ({img.width} × {img.height} px)"
                        )
                        continue

                    logger.info(
                        f"Image ({i + 1}) on page ({index + 1}) / ({len(page_contents)}): "
                        f"Converting to text"
                    )

                    text = image_to_text_callback(img)

                    if text:
                        page_image_texts.append(f"[Image] {text}")
                    else:
                        logger.warning(
                            f"Image ({i + 1}) on page ({index + 1}) / ({len(page_contents)}): "
                            f"Returned no text"
                        )
            except Exception as e:
                logger.warning(
                    f"Image ({i + 1}) on page ({index + 1}) / ({len(page_contents)}): "
                    f"Failed to extract text: {e}"
                )

        all_image_texts.append(page_image_texts)

    return all_image_texts


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
        doc: fitz.Document,
        decoder_settings: DecoderSettings,
) -> List[PdfPageContent]:
    """
    Get PDF page contents.
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
        ocr_strategy_to_apply: OcrStrategy

        if decoder_settings.ocr_strategy == OcrStrategy.AUTO:
            if len(page_content.text) >= decoder_settings.ocr_auto_threshold:
                ocr_strategy_to_apply = OcrStrategy.RELAXED
                logger.info(f"- OCR strategy: 'auto' resolved to 'relaxed' (threshold: {decoder_settings.ocr_auto_threshold} characters)")
            else:
                ocr_strategy_to_apply = OcrStrategy.STRICT
                logger.info(f"- OCR strategy: 'auto' resolved to 'strict' (threshold: {decoder_settings.ocr_auto_threshold} characters)")
        else:
            ocr_strategy_to_apply = decoder_settings.ocr_strategy
            logger.info(f"- OCR strategy: '{ocr_strategy_to_apply.value}'")

        if ocr_strategy_to_apply == OcrStrategy.STRICT:
            # Replace page content with only one full-page image.
            logger.info(f"- IGNORING ({len(page_content.image_blocks)}) image(s)")
            logger.info(f"- IGNORING ({len(page_content.text)}) character(s) in ({len(page_content.text_blocks)}) text block(s)")
            logger.info(f"- Decoding full-page image (rendered at {OCR_STRATEGY_STRICT_PAGE_DPI} DPI) ")
            page_content = PdfPageContent(
                text="",
                layout_image_bytes=[page.get_pixmap(dpi=OCR_STRATEGY_STRICT_PAGE_DPI).tobytes()],
            )

        elif ocr_strategy_to_apply == OcrStrategy.RELAXED:
            # Keep page content as-is.
            logger.info(f"- Decoding ({len(page_content.image_blocks)}) image(s)")
            logger.info(f"- Decoding ({len(page_content.text)}) character(s) in ({len(page_content.text_blocks)}) text block(s)")

            num_background_images: int = len(page_content.image_objects) - len(page_content.image_blocks)
            if num_background_images > 0:
                logger.warning(f"- IGNORING ({num_background_images}) background image(s)")

            if page_content.vector_blocks:
                logger.warning(f"- IGNORING ({len(page_content.vector_blocks)}) vector diagram(s)")

        else:
            raise ValueError(f"Invalid or unhandled OCR strategy: '{ocr_strategy_to_apply.value}'")

        page_contents.append(page_content)

    return page_contents
