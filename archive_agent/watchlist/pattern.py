#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import os
import glob
from typing import List

logger = logging.getLogger(__name__)


def resolve_pattern(pattern: str) -> List[str]:
    """
    Resolve file system search pattern to absolute file paths.
    :param pattern: Pattern.
    :return: List of absolute file paths.
    """
    return sorted([
        os.path.abspath(file_path)
        for file_path in glob.glob(pattern, recursive=True)
        if os.path.isfile(file_path)
    ])


def validate_pattern(pattern: str) -> str:
    """
    Validate file system search pattern (expanded home directory).
    :param pattern: Pattern.
    :return: Pattern (expanded home directory).
    :raises typer.Exit: If pattern is invalid.
    """
    pattern = os.path.expanduser(pattern)
    if os.path.isabs(pattern):
        return pattern
    else:
        logger.error(f"Invalid pattern: {pattern}")
        raise typer.Exit(code=1)
