#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import io
from typing import Callable, Optional, List, Any

# noinspection PyPackageRequirements
import fitz
import pymupdf4llm
from PIL import Image

from archive_agent.util.format import format_file
from archive_agent.util.text import logger


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
        result_parts: list[str] = []

        # Extract all markdown text from document
        try:
            text = pymupdf4llm.to_markdown(file_path).strip()
            if text:
                logger.info(f"Extracted ({len(text)}) characters from document")
                result_parts.append(text)
            else:
                logger.warning("Document appears to contain no extractable text")

        except Exception as e:
            logger.warning(f"Failed to extract markdown text: {e}")
            return None

        # Open document with PyMuPDF to get images
        pages: List[Any] = [page for page in fitz.open(file_path)]

        for page_index, page in enumerate(pages):
            logger.info(f"Processing page ({page_index + 1}) / ({len(pages)})...")
            image_blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 1]

            for img_index, img_block in enumerate(image_blocks):
                logger.info(f"Processing image ({img_index + 1}) / ({len(image_blocks)})...")
                image_bytes = img_block["image"]

                try:
                    with io.BytesIO(image_bytes) as img_io:

                        with Image.open(img_io) as img:
                            image_text = image_to_text_callback(img)

                            if image_text is None:
                                logger.warning(f"Failed to convert image")
                                return None

                            result_parts.append(f"[Image] {image_text}")

                except Exception as e:
                    logger.warning(f"Failed to load image from {format_file(file_path)}: {e}")
                    return None

        return "\n\n".join(result_parts)

    except Exception as e:
        logger.warning(f"Failed to load {format_file(file_path)}: {e}")
        return None
