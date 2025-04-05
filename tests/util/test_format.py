#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.util.format import format_time


def test_format_time():
    assert format_time(1743856496.0) == "2025-04-05 12:34:56"
