#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.util.format import format_time, format_file, format_filename_short


def test_format_time():
    assert format_time(1743856496.0) == "2025-04-05 12:34:56"


def test_format_file():
    assert format_file("/home/user/Hello World.md") in [
        "file:///home/user/Hello%20World.md",  # Linux
        "file:///System/Volumes/Data/home/user/Hello%20World.md",  # macOS
    ]


def test_format_filename_short():
    # Test short filename (no truncation needed)
    assert format_filename_short("/path/to/file.txt") == "file.txt"

    # Test long filename that needs truncation
    long_name = "/path/to/very_long_filename_that_exceeds_the_maximum_length_limit.txt"
    result = format_filename_short(long_name, max_length=20)
    assert len(result) == 20
    assert result == "very_lon...limit.txt"
    assert "..." in result

    # Test edge case with very short max_length
    result_short = format_filename_short("/path/to/file.txt", max_length=5)
    assert result_short == "f...t"

    # Test exact length match
    assert format_filename_short(
        "/path/to/exactly48characters_filename_test_case.txt", max_length=48
    ) == "exactly48characters_filename_test_case.txt"
