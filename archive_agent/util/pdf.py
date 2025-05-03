#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import io
import os
from typing import Optional, List, Set, Tuple, Any

# noinspection PyPackageRequirements
import fitz
from PIL import Image

from archive_agent.config.DecoderSettings import OcrStrategy
from archive_agent.util.format import format_file
from archive_agent.util.image import ImageToTextCallback
from archive_agent.util.image_debugger import show_images, IndexedImage
from archive_agent.util.pdf_util import PdfPageContent, analyze_page_objects, log_page_analysis

logger = logging.getLogger(__name__)


IMAGE_DEBUGGER: bool = True if os.environ.get("ARCHIVE_AGENT_IMAGE_DEBUGGER", False) else False


TINY_IMAGE_WIDTH_THRESHOLD: int = 32
TINY_IMAGE_HEIGHT_THRESHOLD: int = 32


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
        ocr_strategy: OcrStrategy,
) -> Optional[str]:
    """
    Load PDF document, extract layout text and images, convert images to text, and assemble the final document content.
    :param file_path: File path.
    :param image_to_text_callback: Optional image-to-text callback.
    :param ocr_strategy: OCR strategy.
    :return: Full document text if successful, None otherwise.
    """
    try:
        doc: fitz.Document = fitz.open(file_path)

        logger.info(f"Processing: OCR strategy: {ocr_strategy}")

        if ocr_strategy == OcrStrategy.STRICT.value:
            page_contents: List[PdfPageContent] = []
            indexed_images: List[IndexedImage] = []

            pages: List[Any] = [page for page in doc]

            for page_index, page in enumerate(pages):
                try:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes()
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

                    # Create a fake page content with only one full-page image
                    content = PdfPageContent(text="", layout_image_bytes=[img_bytes])
                    page_contents.append(content)

                    # Include in visual debugger images
                    indexed_images.append((img, page_index + 1, 1))
                except Exception as e:
                    logger.warning(f"OCR strategy: strict: Failed to process page ({page_index + 1}): {e}")
                    # Add empty fallback content
                    page_contents.append(PdfPageContent(text="", layout_image_bytes=[]))

        elif ocr_strategy == OcrStrategy.RELAXED.value:
            page_contents, indexed_images = extract_page_contents_with_images(doc)

        else:
            raise ValueError(f"Invalid OCR strategy: {ocr_strategy}")

        for index, content in enumerate(page_contents):
            log_page_analysis(index, len(page_contents), content)

        if IMAGE_DEBUGGER and indexed_images:
            show_images(indexed_images)

        image_texts_per_page = None

        if len(indexed_images) > 0:
            if image_to_text_callback is None:
                logger.warning(f"Image vision is DISABLED in your current configuration")
                logger.warning(f"IGNORING ({len(indexed_images)}) PDF document image(s)")
            else:
                image_texts_per_page = extract_text_from_images_per_page(
                    file_path,
                    page_contents,
                    image_to_text_callback,
                )

        return build_document_text_from_pages(page_contents, image_texts_per_page)

    except Exception as e:
        logger.warning(f"Failed to load {format_file(file_path)}: {e}")
        return None


def extract_page_contents_with_images(
        doc: fitz.Document
) -> Tuple[List[PdfPageContent], List[IndexedImage]]:
    """
    Analyze all pages in the PDF and extract both layout content and indexed layout images.
    :param doc: Opened PyMuPDF document.
    :return: Tuple of page contents and image triplets (image, page number, image index).
    """
    page_contents: List[PdfPageContent] = []
    indexed_images: List[IndexedImage] = []

    pages: List[Any] = [page for page in doc]

    for page_index, page in enumerate(pages):
        content: PdfPageContent = analyze_page_objects(page)
        page_contents.append(content)

        for image_index, b in enumerate(content.layout_image_bytes):
            try:
                img = Image.open(io.BytesIO(b)).convert("RGB")
                indexed_images.append((img, page_index + 1, image_index + 1))
            except Exception as e:
                logger.warning(
                    f"Failed to decode image ({image_index + 1}) "
                    f"on page ({page_index + 1}) / ({len(pages)}): {e}"
                )

    return page_contents, indexed_images


def extract_text_from_images_per_page(
        file_path: str,
        contents: List[PdfPageContent],
        image_to_text_callback: ImageToTextCallback,
) -> List[List[str]]:
    """
    Extract image-based text descriptions for each page.
    :param file_path: File path (used for logging only).
    :param contents: List of PageContent instances.
    :param image_to_text_callback: Image-to-text callback.
    :return: List of text results per page (one list of strings per page).
    """
    all_image_texts: List[List[str]] = []

    for index, content in enumerate(contents):
        page_image_texts: List[str] = []
        logger.info(f"Processing {format_file(file_path)}")

        for i, img_bytes in enumerate(content.layout_image_bytes):
            try:
                with Image.open(io.BytesIO(img_bytes)) as img:
                    if img.width <= TINY_IMAGE_WIDTH_THRESHOLD or img.height <= TINY_IMAGE_HEIGHT_THRESHOLD:
                        logger.warning(
                            f"Image ({i + 1}) on page ({index + 1}) / ({len(contents)}): "
                            f"Ignored because it's tiny ({img.width} × {img.height} px)"
                        )
                        continue

                    logger.info(
                        f"Image ({i + 1}) on page ({index + 1}) / ({len(contents)}): "
                        f"Converting to text"
                    )

                    text = image_to_text_callback(img)

                    if text:
                        page_image_texts.append(f"[Image] {text}")
                    else:
                        logger.warning(
                            f"Image ({i + 1}) on page ({index + 1}) / ({len(contents)}): "
                            f"Returned no text"
                        )
            except Exception as e:
                logger.warning(
                    f"Image ({i + 1}) on page ({index + 1}) / ({len(contents)}): "
                    f"Failed to extract text: {e}"
                )

        all_image_texts.append(page_image_texts)

    return all_image_texts


def build_document_text_from_pages(
        contents: List[PdfPageContent],
        image_texts_per_page: Optional[List[List[str]]] = None
) -> Optional[str]:
    """
    Build the final document text by combining layout text and image-derived text.

    :param contents: List of PageContent instances.
    :param image_texts_per_page: Optional image text results per page (must align by index if provided).
    :return: Text.
    """
    result_parts: List[str] = []

    if image_texts_per_page is not None:
        assert len(contents) == len(image_texts_per_page)

    for idx, content in enumerate(contents):
        page_parts: List[str] = []

        if image_texts_per_page is not None:
            page_parts.extend(image_texts_per_page[idx])

        if content.text:
            page_parts.append(content.text)

        if page_parts:
            result_parts.append("\n\n".join(page_parts))

    return "\n\n".join(result_parts) if result_parts else ""
