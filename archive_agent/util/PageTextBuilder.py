#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import Optional, List

from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.text_util import splitlines_exact


class PageTextBuilder:

    def __init__(self, text: Optional[str] = None):
        """
        Initialize page-based text builder.
        :param text: Text (optional).
        """
        self._lines: List[str] = []
        self._page_numbers: List[int] = []

        self._current_page_number = 1

        if text is not None:
            for line in splitlines_exact(text):
                self.push(line)

    def push(self, line: str = "", page_number: Optional[int] = None):
        """
        Push text line with optional page number.
        Current page number is used if no page number is given.
        :param line: Text line (optional, defaults to empty line).
        :param page_number: Page number (optional).
        """
        if page_number is None:
            page_number = self._current_page_number
        else:
            self._current_page_number = page_number

        self._lines.append(line)
        self._page_numbers.append(page_number)

    def getDocumentContent(self) -> Optional[DocumentContent]:
        """
        Get document content.
        :return: Document content, or None if empty.
        """
        if len(self._lines) == 0:
            return None

        return DocumentContent.from_lines(lines=self._lines, pages_per_line=self._page_numbers)
