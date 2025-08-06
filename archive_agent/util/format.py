# archive_agent/util/format.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
import os
import pathlib
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

from qdrant_client.http.models import ScoredPoint, PointStruct
from archive_agent.db.QdrantSchema import parse_payload


def format_time(timestamp: float) -> str:
    """
    Format timestamp as UTC.
    :param timestamp: Timestamp.
    :return: Timestamp formatted as UTC.
    """
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_filename_short(file_path: str, max_length: int = 80) -> str:
    """
    Format filename for display, shortening if necessary.
    Strips the path and replaces middle part with ... if length exceeds max_length.
    :param file_path: Full file path.
    :param max_length: Maximum length for display.
    :return: Shortened filename for display.
    """
    filename = os.path.basename(file_path)
    if len(filename) <= max_length:
        return filename

    # If still too long, truncate in the middle
    if max_length < 5:  # Need at least 5 chars for "a...b"
        return filename[:max_length]

    # Calculate how many chars to show on each side
    side_chars = (max_length - 3) // 2  # 3 for "..."
    left_chars = side_chars
    right_chars = max_length - 3 - left_chars

    return f"{filename[:left_chars]}...{filename[-right_chars:]}"


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


def get_point_page_line_info(point: ScoredPoint | PointStruct) -> Optional[str]:
    """
    Get point page or line info
    :param point: Point.
    :return: Page or line info (optional).
    """
    model = parse_payload(point.payload)
    if model.page_range is not None and model.page_range:
        r = model.page_range
        return f"pages {r[0]}–{r[-1]}" if len(r) > 1 else f"page {r[0]}"
    elif model.line_range is not None and model.line_range:
        r = model.line_range
        return f"lines {r[0]}–{r[-1]}" if len(r) > 1 else f"line {r[0]}"
    else:
        return None


def get_point_reference_info(logger: Logger, point: ScoredPoint, verbose: bool) -> str:
    """
    Get point reference info.
    NOTE: Chunks that were added before v5.0.0 don't have the fields `page_range` and `line_range.
          This is handled gracefully in here.
    :param logger: Logger.
    :param point: Point.
    :param verbose: Append additional chunk info
    :return: Point reference info.
    """
    model = parse_payload(point.payload)
    chunk_info = f"chunk {model.chunk_index + 1}/{model.chunks_total}"

    page_line_info = get_point_page_line_info(point)

    if page_line_info is not None:
        origin_info = f"{page_line_info}"
        if verbose:
            origin_info += f" · {chunk_info}"
    else:
        origin_info = f"{chunk_info}"

    reference_info = f"{format_file(model.file_path)} · {origin_info}"

    if verbose:
        reference_info += f" · {format_time(model.file_mtime)}"

    if page_line_info is None:
        logger.warning(
            f"Chunk is missing lines and pages info:\n"
            f"{point.payload}"
        )

    return reference_info


def format_chunk_brief(chunk: str, max_len: int = 160) -> str:
    """
    Format chunk as brief string.
    :param chunk: Chunk.
    :param max_len: Maximum string length.
    :return: Brief string.
    """
    chunk_brief = chunk.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return f"{chunk_brief[:max_len]}…" if len(chunk_brief) > max_len else f"{chunk_brief}"
