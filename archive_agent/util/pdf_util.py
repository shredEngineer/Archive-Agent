#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, List

# noinspection PyPackageRequirements
import fitz

logger = logging.getLogger(__name__)


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


def get_pdf_page_content(page: fitz.Page) -> PdfPageContent:
    """
    Get PDF page content.
    :param page: PDF page.
    :return: PDF page content.
    """

    # noinspection PyUnresolvedReferences
    text: str = page.get_text("text").strip()

    image_objects: List[ImageObject] = page.get_images(full=True)

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

    return PdfPageContent(
        text=text,
        layout_image_bytes=layout_image_bytes,
        text_blocks=text_blocks,
        image_blocks=image_blocks,
        vector_blocks=vector_blocks,
        other_blocks=other_blocks,
        image_objects=image_objects,
    )
