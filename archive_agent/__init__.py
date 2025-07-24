#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from importlib.metadata import version, PackageNotFoundError

from rich.logging import RichHandler
import logging

from rich.highlighter import ReprHighlighter
from rich.text import Text
import re


class CustomLogHighlighter(ReprHighlighter):
    """
    A highlighter that preserves Rich's useful formatting (e.g., numbers, strings),
    while removing distracting syntax tokens and adding custom semantic highlights.
    """

    def __init__(self) -> None:
        """
        Initialize with clean keyword-to-style mapping.
        """
        super().__init__()

        self.custom_keywords: dict[str, str] = {
            "included": "cyan3",
            "excluded": "deep_pink1",
            "added": "bold green",
            "removed": "bold red",
            "changed": "bold orange3",
        }

        self.unwanted_words: tuple[str, ...] = (
            "pattern",
            "file",
            "name",
            "profile",
            "chunk",
            "token",
            "vector",
            "image",
            "character",
            "block",
        )

    def highlight(self, text: Text) -> None:
        """
        Apply cleaned ReprHighlighter base, strip undesired styles, and
        apply custom keyword-based styling.

        :param text: The rich Text object to be highlighted.
        """
        # Apply Rich's default formatting (numbers, strings, etc.)
        super().highlight(text)

        raw_text = text.plain

        # Remove Rich's default styling from unwanted keywords
        for word in self.unwanted_words:
            for match in re.finditer(rf"\b{re.escape(word)}\b", raw_text, re.IGNORECASE):
                text.stylize("default", match.start(), match.end())

        # Apply your custom keyword styles
        for word, style in self.custom_keywords.items():
            for match in re.finditer(rf"\b{re.escape(word)}\b", raw_text, re.IGNORECASE):
                text.stylize(style, match.start(), match.end())


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        RichHandler(
            markup=False,
            rich_tracebacks=True,
            highlighter=CustomLogHighlighter(),
            show_path=False,  # Enable this for file:line traceback
        )
    ]
)

logger = logging.getLogger()

# Get version
try:
    __version__ = version("archive-agent")
except PackageNotFoundError:
    __version__ = "unknown"

logger.info(f"⚡ Archive Agent: Version {__version__}")
