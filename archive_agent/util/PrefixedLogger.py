#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
from typing import Any


class PrefixedLogger(Logger):
    """
    A logger that prepends a prefix to all log messages while delegating everything to the parent logger.
    """

    def __init__(self, prefix: str, parent_logger: Logger):
        """
        Initialize the prefixed logger.
        :param prefix: Prefix to prepend to all messages.
        :param parent_logger: Parent logger to delegate to.
        """
        # Initialize with parent's name and level, but don't add handlers
        super().__init__(parent_logger.name, parent_logger.level)
        self.prefix = prefix
        self.parent_logger = parent_logger

        # Clear any handlers that might have been added during initialization
        self.handlers = []
        self.propagate = False

    def _log(self, level: int, msg: Any, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        """
        Override _log to prepend prefix and delegate to parent logger.
        """
        prefixed_msg = f"[{self.prefix}] {msg}"
        # Call parent logger's _log method directly
        self.parent_logger._log(level, prefixed_msg, args, exc_info=exc_info, extra=extra, stack_info=stack_info, stacklevel=stacklevel)

    def __getattr__(self, name):
        """
        Delegate any other attributes to the parent logger.
        """
        return getattr(self.parent_logger, name)
