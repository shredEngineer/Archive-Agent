#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class DocumentContent:
    """
    Document content with pages (for page-based documents, e.g. `.pdf`) or lines (for line-based documents, e.g. `.txt`) info.
    """
    text: str  # Text (page- or line-based).
    lines_per_line: Optional[List[int]] = None  # Line-based: Absolute line number for each line of `text`.
    pages_per_line: Optional[List[int]] = None  # Page-based: Absolute page number for each line of `text`.

    def __post_init__(self):
        """
        Sanity checks
        """
        # NOTE: Chunks that were added before v5.0.0 don't have the fields `page_range` and `line_range.
        #       This is handled gracefully in `get_point_reference_info()`.
        if self.lines_per_line is None and self.pages_per_line is None:
            pass

        # NOTE: Beginning with v5.0.0, source document pages or lines info is included in point payload.
        #       Exactly one of the fields must be set.
        if self.lines_per_line is not None and self.pages_per_line is not None:
            raise ValueError("Only one of `pages_per_line` or `lines_per_line` can be set")

        # Line-based: Each (relative) text line must correspond to *some* (absolute) document line…
        if self.lines_per_line is not None and len(self.lines_per_line) != len(self.text.splitlines()):
            raise ValueError("`lines_per_line` length must match text lines")

        # Page-based: Each text line must have been extracted from *some* document page…
        if self.pages_per_line is not None and len(self.pages_per_line) != len(self.text.splitlines()):
            raise ValueError("`pages_per_line` length must match text lines")
