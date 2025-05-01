#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.util.text_split_sentences import split_sentences


def test_split_sentences_output():
    with open("./tests/util/test_data/test_unsanitized.txt", "r", encoding="utf-8") as f:
        raw_text = f.read()

    with open("./tests/util/test_data/test_sanitized.txt", "r", encoding="utf-8") as f:
        expected_text = f.read()

    result = split_sentences(raw_text)

    # Join sentence blocks into output form ("" = paragraph break)
    joined = "\n".join(result)

    assert joined.strip() == expected_text.strip()
