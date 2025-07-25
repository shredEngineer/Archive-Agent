#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
from dataclasses import dataclass
from typing import Optional, List

from archive_agent.util.text_util import splitlines_exact


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
        text_lines = splitlines_exact(self.text)

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
        if self.lines_per_line is not None and len(self.lines_per_line) != len(text_lines):
            raise ValueError(
                f"`lines_per_line` length must match text lines:\n"
                f"text={json.dumps(text_lines, indent=2, default=str)}\n"
                f"lines_per_line={json.dumps(self.lines_per_line, indent=2, default=str)}\n"
            )

        # Page-based: Each text line must have been extracted from *some* document page…
        if self.pages_per_line is not None and len(self.pages_per_line) != len(text_lines):
            raise ValueError(
                f"`pages_per_line` length must match text lines:\n"
                f"text={json.dumps(text_lines, indent=2, default=str)}\n"
                f"lines_per_line={json.dumps(self.pages_per_line, indent=2, default=str)}\n"
            )
