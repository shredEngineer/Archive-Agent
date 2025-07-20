#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import os
import pathlib
import urllib.parse
from datetime import datetime, timezone

from qdrant_client.http.models import ScoredPoint

logger = logging.getLogger(__name__)


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


def get_point_reference_info(point: ScoredPoint) -> str:
    """
    Get point reference info.
    NOTE: Chunks that were added before v5.0.0 don't have the fields `page_range` and `line_range.
          This is handled gracefully in here.
    :param point: Point.
    :return: Point reference info.
    """
    assert point.payload is not None  # makes pyright happy

    chunk_info = f"chunk {point.payload['chunk_index'] + 1}/{point.payload['chunks_total']}"

    if 'page_range' in point.payload and point.payload['page_range']:
        r = point.payload['page_range']
        page_line_info = f"pages {r[0]}–{r[-1]}]" if len(r) > 1 else f"page {r[0]}"

    elif 'line_range' in point.payload and point.payload['line_range']:
        r = point.payload['line_range']
        page_line_info = f"lines {r[0]}–{r[-1]}" if len(r) > 1 else f"line {r[0]}"

    else:
        page_line_info = None

    origin_info = f"{page_line_info} ({chunk_info})" if page_line_info is not None else f"({chunk_info})"

    reference_info = f"{format_file(point.payload['file_path'])} {origin_info} ({format_time(point.payload['file_mtime'])})"

    if page_line_info is None:
        logger.warning(f"Chunk added by Archive Agent < 5.0.0 is missing lines and pages info: {reference_info}")

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
