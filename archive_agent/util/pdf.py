#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import io
from typing import Optional, List, Set, Any

# noinspection PyPackageRequirements
import fitz

from PIL import Image

from archive_agent.config.DecoderSettings import OcrStrategy, DecoderSettings
from archive_agent.util.format import format_file
from archive_agent.util.image import ImageToTextCallback
from archive_agent.util.pdf_util import PdfPageContent, get_pdf_page_content

logger = logging.getLogger(__name__)


TINY_IMAGE_WIDTH_THRESHOLD: int = 32
TINY_IMAGE_HEIGHT_THRESHOLD: int = 32

OCR_STRATEGY_STRICT_PAGE_DPI: int = 300


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
) -> Optional[str]:
    """
    Load PDF document.
    :param file_path: File path.
    :param image_to_text_callback: Optional image-to-text callback.
    :param decoder_settings: Decoder settings.
    :return: PDF document text if successful, None otherwise.
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
        if decoder_settings.ocr_strategy == OcrStrategy.AUTO.value:
            if len(page_content.text) >= decoder_settings.ocr_auto_threshold:
                ocr_strategy_resolved = OcrStrategy.RELAXED.value
                logger.info(f"- OCR strategy: 'auto' resolved to 'relaxed' (threshold: {decoder_settings.ocr_auto_threshold} characters)")
            else:
                ocr_strategy_resolved = OcrStrategy.STRICT.value
                logger.info(f"- OCR strategy: 'auto' resolved to 'strict' (threshold: {decoder_settings.ocr_auto_threshold} characters)")
        else:
            ocr_strategy_resolved = decoder_settings.ocr_strategy
            logger.info(f"- OCR strategy: '{ocr_strategy_resolved}'")

        if ocr_strategy_resolved == OcrStrategy.STRICT.value:
            # Replace page content with only one full-page image.
            logger.info(f"- IGNORING ({len(page_content.image_blocks)}) image(s)")
            logger.info(f"- IGNORING ({len(page_content.text)}) character(s) in ({len(page_content.text_blocks)}) text block(s)")
            logger.info(f"- Decoding full-page image (rendered at {OCR_STRATEGY_STRICT_PAGE_DPI} DPI) ")
            page_content = PdfPageContent(
                text="",
                layout_image_bytes=[page.get_pixmap(dpi=OCR_STRATEGY_STRICT_PAGE_DPI).tobytes()],
            )

        elif ocr_strategy_resolved == OcrStrategy.RELAXED.value:
            # Keep page content as-is.
            logger.info(f"- Decoding ({len(page_content.image_blocks)}) image(s)")
            logger.info(f"- Decoding ({len(page_content.text)}) character(s) in ({len(page_content.text_blocks)}) text block(s)")

            num_background_images: int = len(page_content.image_objects) - len(page_content.image_blocks)
            if num_background_images > 0:
                logger.warning(f"- IGNORING ({num_background_images}) background image(s)")

            if page_content.vector_blocks:
                logger.warning(f"- IGNORING ({len(page_content.vector_blocks)}) vector diagram(s)")

        else:
            raise ValueError(f"Invalid OCR strategy: '{decoder_settings.ocr_strategy}'")

        page_contents.append(page_content)

    return page_contents


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


def build_document_text_from_pages(
        page_contents: List[PdfPageContent],
        image_texts_per_page: Optional[List[List[str]]] = None
) -> Optional[str]:
    """
    Build PDF document text by combining layout text and image text.
    :param page_contents: PDF page contents.
    :param image_texts_per_page: Optional image text results per page (must align by index if provided).
    :return: PDF document text.
    """
    result_parts: List[str] = []

    if image_texts_per_page is not None:
        assert len(page_contents) == len(image_texts_per_page)

    for idx, content in enumerate(page_contents):
        page_parts: List[str] = []

        # TODO: Build {PDF page number : PDF line number} array and pass through to `load_pdf_document`, then return it from there — see #15

        if image_texts_per_page is not None:
            page_parts.extend(image_texts_per_page[idx])

        if content.text:
            page_parts.append(content.text)

        if page_parts:
            result_parts.append("\n\n".join(page_parts))

    return "\n\n".join(result_parts) if result_parts else ""
