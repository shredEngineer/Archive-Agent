#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from datetime import datetime, timezone
import pathlib
import urllib.parse


def format_time(timestamp: float) -> str:
    """
    Format timestamp as UTC.
    :param timestamp: Timestamp.
    :return: Timestamp formatted as UTC.
    """
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_file(file_path: str | pathlib.Path) -> str:
    """
    Format file path as file:// URI syntax.

    :param file_path: Local file path.
    :return: File path formatted as file:// URI.
    """
    abs_path = pathlib.Path(file_path).resolve()
    return f"file://{urllib.parse.quote(str(abs_path))}"
