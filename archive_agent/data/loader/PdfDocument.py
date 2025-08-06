from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, List, Dict

from archive_agent.config.DecoderSettings import OcrStrategy


@dataclass
class PdfPageContent:
    """
    PDF page content.
    """
    text: str = ""
    layout_image_bytes: List[bytes] = field(default_factory=list)
    ocr_strategy: OcrStrategy = field(default=OcrStrategy.AUTO)
    # Block counts for logging purposes
    text_block_count: int = 0
    image_block_count: int = 0
    vector_block_count: int = 0
    background_image_count: int = 0


class PdfPage(ABC):
    """
    Abstract interface for PDF page operations.
    """

    @abstractmethod
    def get_text(self) -> str:
        """
        Extract text content from the page.
        :return: Text content.
        """
        pass

    @abstractmethod
    def get_image_bytes(self) -> List[bytes]:
        """
        Extract image bytes from the page.
        :return: List of image bytes.
        """
        pass

    @abstractmethod
    def get_counts(self) -> Dict[str, int]:
        """
        Get counts of different block types for logging.
        :return: Dictionary with keys: text_blocks, image_blocks, vector_blocks, background_images.
        """
        pass

    @abstractmethod
    def get_pixmap(self, dpi: int) -> bytes:
        """
        Render page as pixmap and return bytes.
        :param dpi: DPI for rendering.
        :return: Pixmap bytes.
        """
        pass

    def get_content(self) -> PdfPageContent:
        """
        Get complete page content including text, images, and metadata.
        :return: PDF page content.
        """
        text: str = self.get_text()
        layout_image_bytes: List[bytes] = self.get_image_bytes()
        block_counts: Dict[str, int] = self.get_counts()

        return PdfPageContent(
            text=text,
            layout_image_bytes=layout_image_bytes,
            text_block_count=block_counts.get("text_blocks", 0),
            image_block_count=block_counts.get("image_blocks", 0),
            vector_block_count=block_counts.get("vector_blocks", 0),
            background_image_count=block_counts.get("background_images", 0),
        )

    def get_full_page_pixmap(self, dpi: int) -> bytes:
        """
        Helper method to get full-page pixmap (common STRICT OCR operation).
        :param dpi: DPI for rendering.
        :return: Full-page pixmap bytes.
        """
        return self.get_pixmap(dpi)


class PdfDocument(ABC):
    """
    Abstract interface for PDF document operations.
    """

    @abstractmethod
    def __iter__(self) -> Iterator[PdfPage]:
        """
        Iterate over pages in the document.
        :return: Iterator of PDF pages.
        """
        pass
