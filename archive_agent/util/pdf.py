#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import io
from typing import Callable, Optional

# noinspection PyPackageRequirements
import fitz
import pymupdf4llm
from PIL import Image

from util.format import format_file
from util.text import logger


def load_pdf_document(
        file_path: str,
        image_to_text_callback: Callable[[Image.Image], Optional[str]]
) -> Optional[str]:
    """
    Load PDF document, extracting text and images in order.
    :param file_path: File path.
    :param image_to_text_callback: Function converting Image to text.
    :return: Text with image descriptions if successful, None otherwise.
    """
    try:
        # Extract markdown text using pymupdf4llm
        md_text = pymupdf4llm.to_markdown(file_path).split("\n")

        # Open document with PyMuPDF
        doc = fitz.open(file_path)

        result_parts: list[str] = []

        # noinspection PyTypeChecker
        for page_index, page in enumerate(doc):
            logger.info(f"Processing page ({page_index + 1}) / ({len(doc)})...")

            # Append markdown content line by line
            page_md_lines = [line for line in md_text if f"Page {page_index + 1}" in line]
            if page_md_lines:
                result_parts.extend(page_md_lines)
            else:
                logger.warning(f"Page appears to be a scanned page without OCR")

            # Extract images from page
            image_blocks = [
                b for b in page.get_text("dict")["blocks"] if b["type"] == 1
            ]
            for img_index, img_block in enumerate(image_blocks, start=1):
                logger.info(f"Processing image ({img_index}) on page ({page_index + 1}) / ({len(doc)})...")
                image_bytes = img_block["image"]
                try:
                    with io.BytesIO(image_bytes) as img_io:
                        with Image.open(img_io) as img:
                            image_text = image_to_text_callback(img)
                            if image_text is None:
                                logger.warning(f"Failed to convert image")
                                return None
                            result_parts.append(" : ".join([
                                f"[Image ({img_index}) on page ({page_index + 1}) / ({len(doc)})]"
                                f"{image_text}",
                            ]))
                except Exception as e:
                    logger.warning(f"Failed to load {format_file(file_path)}: {e}")
                    return None

        return "\n\n".join(result_parts)

    except Exception as e:
        logger.warning(f"Failed to load {format_file(file_path)}: {e}")
        return None
