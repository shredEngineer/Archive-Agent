#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from datetime import datetime, timezone


def format_time(timestamp: float) -> str:
    """
    Format timestamp as UTC.
    :param timestamp: Timestamp.
    :return: Timestamp formatted as UTC.
    """
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime('%Y-%m-%d %H:%M:%S')
