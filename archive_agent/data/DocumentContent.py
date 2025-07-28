#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
from dataclasses import dataclass, field
from typing import Optional, List

from archive_agent.util.text_util import splitlines_exact


ReferenceList = List[int]


@dataclass
class DocumentContent:
    """
    Document content with pages (for page-based documents, e.g. `.pdf`) or lines (for line-based documents, e.g. `.txt`) info.
    """

    # Both `text` and `lines` are automatically synced whenever one of them is set.
    _text: str = field(init=False, repr=False)
    _lines: List[str] = field(init=False, repr=False)

    lines_per_line: Optional[ReferenceList] = None  # Line-based: Absolute line number for each line of `text`.
    pages_per_line: Optional[ReferenceList] = None  # Page-based: Absolute page number for each line of `text`.

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = text
        self._lines = splitlines_exact(text)

    @property
    def lines(self) -> List[str]:
        return self._lines

    @lines.setter
    def lines(self, lines: List[str]) -> None:
        self._lines = lines
        self._text = "\n".join(lines)

    def validate(self):
        # NOTE: Chunks that were added before v5.0.0 don't have the fields `page_range` and `line_range.
        #       This is handled gracefully in `get_point_reference_info()`.
        #       HOWEVER, since the code constructing this object is beyond v5.0.0, it MUST include one.
        if self.lines_per_line is None and self.pages_per_line is None:
            raise ValueError("Require exactly one of `pages_per_line` or `lines_per_line`")

        # NOTE: Beginning with v5.0.0, source document pages or lines info is included in point payload.
        #       Exactly one of the fields must be set.
        if self.lines_per_line is not None and self.pages_per_line is not None:
            raise ValueError("Only one of `pages_per_line` or `lines_per_line` can be set")

        # Line-based: Each (relative) text line must correspond to *some* (absolute) document line…
        if self.lines_per_line is not None and len(self.lines_per_line) != len(self.lines):
            raise ValueError(
                f"`lines_per_line` length must match text lines:\n"
                f"text={json.dumps(self.lines, indent=2, default=str)}\n"
                f"lines_per_line={json.dumps(self.lines_per_line, indent=2, default=str)}\n"
            )

        # Page-based: Each text line must have been extracted from *some* document page…
        if self.pages_per_line is not None and len(self.pages_per_line) != len(self.lines):
            raise ValueError(
                f"`pages_per_line` length must match text lines:\n"
                f"text={json.dumps(self.lines, indent=2, default=str)}\n"
                f"pages_per_line={json.dumps(self.pages_per_line, indent=2, default=str)}\n"
            )

    @classmethod
    def from_lines(
        cls, lines: List[str], *,
        lines_per_line: Optional[ReferenceList] = None,
        pages_per_line: Optional[ReferenceList] = None,
    ) -> "DocumentContent":
        obj = cls(lines_per_line=lines_per_line, pages_per_line=pages_per_line)
        obj.lines = lines  # Uses setter: updates _text too
        obj.validate()
        return obj

    @classmethod
    def from_text(
        cls, text: str, *,
        lines_per_line: Optional[ReferenceList] = None,
        pages_per_line: Optional[ReferenceList] = None,
    ) -> "DocumentContent":
        obj = cls(lines_per_line=lines_per_line, pages_per_line=pages_per_line)
        obj.text = text  # Uses setter: updates _lines too
        obj.validate()
        return obj

    def strip_lines(self):
        """
        Remove whitespace on each line.
        """
        self.lines = [line.strip() for line in self.lines]

    def get_per_line_references(self) -> ReferenceList:
        """
        Get per-line page or line references.
        """
        is_page_based = self.pages_per_line is not None
        if is_page_based:
            per_line_references = self.pages_per_line
        else:
            per_line_references = self.lines_per_line

        assert per_line_references is not None, "Missing references (WTF, please report)"

        return per_line_references
