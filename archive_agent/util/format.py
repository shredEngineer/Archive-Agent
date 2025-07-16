#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import os
import pathlib
import urllib.parse
from datetime import datetime, timezone


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
    Format file path as file:// URI, escaping special characters like spaces.
    :param file_path: File path.
    :return: File path formatted as file:// URI.
    """
    abs_path = pathlib.Path(file_path).resolve()

    # On Windows, pathlib will produce a path like "C:\path\to\file"
    # We need to convert it to /C:/path/to/file for proper file:// URI
    if os.name == 'nt':
        uri_path = '/' + str(abs_path).replace('\\', '/')
    else:
        uri_path = str(abs_path)

    return f"file://{urllib.parse.quote(uri_path, safe='/')}"


def format_chunk_brief(chunk: str, max_len: int = 160) -> str:
    """
    Format chunk as brief string.
    :param chunk: Chunk.
    :param max_len: Maximum string length.
    :return: Brief string.
    """
    chunk_brief = chunk.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return f"{chunk_brief[:max_len]}…" if len(chunk_brief) > max_len else f"{chunk_brief}"
