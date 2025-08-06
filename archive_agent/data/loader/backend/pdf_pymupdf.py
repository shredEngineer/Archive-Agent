# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from typing import List, Iterator, Dict

# noinspection PyPackageRequirements
import fitz

from archive_agent.data.loader.PdfDocument import PdfDocument, PdfPage


class PyMuPdfDocument(PdfDocument):
    """
    PyMuPDF implementation of PDF document interface.
    """

    def __init__(self, file_path: str):
        """
        Initialize PyMuPDF document.
        :param file_path: Path to PDF file.
        """
        self._doc: fitz.Document = fitz.open(file_path)

    def __iter__(self) -> Iterator[PdfPage]:
        """
        Iterate over pages in the document.
        :return: Iterator of PDF pages.
        """
        for page in self._doc:
            yield PyMuPdfPage(page)


class PyMuPdfPage(PdfPage):
    """
    PyMuPDF implementation of PDF page interface.
    """

    def __init__(self, page: fitz.Page):
        """
        Initialize PyMuPDF page.
        :param page: PyMuPDF page object.
        """
        self._page: fitz.Page = page

    def get_text(self) -> str:
        """
        Extract text content from the page.
        :return: Text content.
        """
        return self._page.get_text("text").strip()  # type: ignore

    def get_image_bytes(self) -> List[bytes]:
        """
        Extract image bytes from the page.
        :return: List of image bytes.
        """
        blocks = self._page.get_text("dict")["blocks"]  # type: ignore
        image_bytes = []

        for block in blocks:
            block_type = block.get("type", "other")
            if block_type == 1:  # Image block
                img = block.get("image")
                if img:
                    image_bytes.append(img)

        return image_bytes

    def get_counts(self) -> Dict[str, int]:
        """
        Get counts of different block types for logging.
        :return: Dictionary with keys: text_blocks, image_blocks, vector_blocks, background_images.
        """
        blocks = self._page.get_text("dict")["blocks"]  # type: ignore
        image_objects = self._page.get_images(full=True)

        text_blocks = 0
        image_blocks = 0
        vector_blocks = 0

        for block in blocks:
            block_type = block.get("type", "other")
            if block_type == 0:
                text_blocks += 1
            elif block_type == 1:
                image_blocks += 1
            elif block_type == 2:
                vector_blocks += 1

        background_images = len(image_objects) - image_blocks

        return {
            "text_blocks": text_blocks,
            "image_blocks": image_blocks,
            "vector_blocks": vector_blocks,
            "background_images": background_images
        }

    def get_pixmap(self, dpi: int) -> bytes:
        """
        Render page as pixmap and return bytes.
        :param dpi: DPI for rendering.
        :return: Pixmap bytes.
        """
        return self._page.get_pixmap(dpi=dpi).tobytes()  # type: ignore


def create_pdf_document(file_path: str) -> PdfDocument:
    """
    Factory function to create a PDF document instance.
    :param file_path: Path to PDF file.
    :return: PDF document instance.
    """
    return PyMuPdfDocument(file_path)
