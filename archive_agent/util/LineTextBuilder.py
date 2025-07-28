#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import Optional, List

from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.util.text_util import splitlines_exact


class LineTextBuilder:

    def __init__(self, text: Optional[str] = None):
        """
        Initialize line-based text builder.
        :param text: Text (optional).
        """
        self._lines: List[str] = []
        self._line_numbers: List[int] = []

        if text is not None:
            for line in splitlines_exact(text):
                self.push(line)

    def push(self, line: str = "", line_number: Optional[int] = None):
        """
        Push text line with optional line number.
        Total line number is incremented and used if no line number is given.
        :param line: Text line (optional, defaults to empty line).
        :param line_number: Line number (optional).
        """
        if line_number is None:
            line_number = len(self._lines) + 1

        self._lines.append(line)
        self._line_numbers.append(line_number)

    def getDocumentContent(self) -> Optional[DocumentContent]:
        """
        Get document content.
        :return: Document content, or None if empty.
        """
        if len(self._lines) == 0:
            return None

        return DocumentContent.from_lines(lines=self._lines, lines_per_line=self._line_numbers)
