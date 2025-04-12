#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.
from dataclasses import dataclass
from typing import Dict, Any, Tuple, List

# noinspection PyPackageRequirements
import fitz

from archive_agent.util.text import logger


LayoutBlock = Dict[str, Any]
ImageObject = Tuple[Any, ...]


@dataclass
class PdfPageContent:
    """
    PDF page content.
    """

    text_blocks: List[LayoutBlock]
    image_blocks: List[LayoutBlock]
    vector_blocks: List[LayoutBlock]
    other_blocks: List[LayoutBlock]
    image_objects: List[ImageObject]
    text: str
    layout_image_bytes: List[bytes]


def analyze_page_objects(page: fitz.Page) -> PdfPageContent:
    """
    Analyze and extract structured content from a PDF page.
    :param page: PDF page.
    :return: PageContent with all relevant elements.
    """
    # noinspection PyUnresolvedReferences
    blocks: List[LayoutBlock] = page.get_text("dict")["blocks"]

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

    image_objects: List[ImageObject] = page.get_images(full=True)
    # noinspection PyUnresolvedReferences
    text: str = page.get_text("text").strip()

    return PdfPageContent(
        text_blocks=text_blocks,
        image_blocks=image_blocks,
        vector_blocks=vector_blocks,
        other_blocks=other_blocks,
        image_objects=image_objects,
        text=text,
        layout_image_bytes=layout_image_bytes
    )


def log_page_analysis(page_index: int, pages_total: int, content: PdfPageContent) -> None:
    """
    Log analysis results and statistics for a page.
    :param page_index: Page index (0-based).
    :param pages_total: Total number of pages.
    :param content: PageContent instance.
    """
    num_background_images: int = len(content.image_objects) - len(content.image_blocks)
    char_count: int = len(content.text)

    logger.info(f"Loading PDF page ({page_index + 1}) / ({pages_total}):")
    logger.info(f"- ({len(content.image_blocks)}) image(s)")
    logger.info(f"- ({char_count}) character(s) in ({len(content.text_blocks)}) text block(s)")

    if num_background_images > 0:
        logger.warning(f"- IGNORING ({num_background_images}) background image(s)")

    if content.vector_blocks:
        logger.warning(f"- IGNORING ({len(content.vector_blocks)}) vector diagram(s)")
