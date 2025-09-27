#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.util.format import format_file

import logging
import json
import re
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def generate_json_filename(question: str, max_length: int = 160) -> str:
    """
    Generate a clean filename from a question for JSON output.
    :param question: The question text.
    :param max_length: Maximum filename length.
    :return: Clean filename with .json extension.
    """
    # Remove or replace problematic characters for filenames
    clean_question = re.sub(r'[<>:"/\\|?*]', '_', question)

    # Replace multiple whitespace with single spaces and strip
    clean_question = re.sub(r'\s+', ' ', clean_question).strip()

    # Replace spaces with underscores
    clean_question = clean_question.replace(' ', '_')

    # Calculate max length for base name (subtract 5 for '.json')
    max_base_length = max_length - 5

    # Truncate if necessary and add [...] if cut off
    if len(clean_question) > max_base_length:
        truncate_length = max_base_length - 5  # subtract 5 for '[...]'
        clean_question = clean_question[:truncate_length] + '[...]'

    return f"{clean_question}.json"


def write_to_json(json_filename: Path, question: str, query_result: Dict[str, Any], answer_text: str) -> None:
    """
    Write query data to JSON.
    NOTE: As of v12.2.0, a corresponding Markdown file (`.md`) containing the answer is also created.

    :param json_filename: JSON filename.
    :param question: Question.
    :param query_result: Query result.
    :param answer_text: Answer text.
    :return: None
    """
    query_data = {
        "question": question,
        "query_result": query_result,
        "answer_text": answer_text
    }

    json_filename.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON file
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(query_data, f, ensure_ascii=False, indent=4)

    logger.info(f"Writing answer to JSON: {format_file(json_filename)}")

    # Write Markdown file with same base name
    md_filename = json_filename.with_suffix(".md")
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(answer_text)

    logger.info(f"Writing answer to Markdown: {format_file(md_filename)}")
