#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging

logger = logging.getLogger(__name__)


class AiChunk:

    @staticmethod
    def get_prompt_chunk(line_numbered_text: str) -> str:
        return "\n".join([
            "Act as a chunking agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to segment the text into semantically coherent chunks.",
            "You must output structured information using the exact response fields described below.",
            "Do not return any explanations, commentary, or additional fields.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `chunk_start_lines`:",
            "    List of line numbers. Each marks the start of a chunk.",
            "    The first value MUST be 1 (the first line).",
            "    The list must be strictly increasing. No duplicates.",
            "",
            "- `headers`:",
            "    List of one-line header strings, one for each chunk, in the same order as `chunk_start_lines`.",
            "    Each header must clearly and succinctly summarize the main topic or content of the chunk in a single line.",
            "    If a chunk starts with a heading, include its topic but clarify if needed.",
            "    Do not use generic headers.",
            "",
            "CHUNKING RULES:",
            "- Review the entire text before deciding chunk boundaries.",
            "- Each chunk MUST be semantically coherent.",
            "- Each chunk SHOULD be about 100 words.",
            "- Chunks must NOT be shorter than 10 lines or 100 words.",
            "- Exception: allow smaller chunks if strictly necessary",
            "  (e.g., at the end of the text, or if the content cannot be grouped larger without breaking coherence).",
            "- Detect structure (e.g., Markdown headings.",
            "- Headings must not be a chunk alone.",
            "- Always group a heading with its following content.",
            "- If a heading and its content are too short, merge with the next section, unless this breaks semantic coherence.",
            "- If two or more headings have little content, group all with the next non-heading content.",
            "- Only create a new chunk if there is a clear semantic or topic boundary.",
            "- Do not chunk line by line.",
            "- Make all chunking decisions after reviewing the entire text.",
            "- If a chunk must exceed the target size to maintain coherence, do so.",
            "- At the end: If the final content is too short, merge with the previous chunk unless this breaks semantic coherence.",
            "",
            "Text with line numbers:",
            "\"\"\"\n" + line_numbered_text + "\n\"\"\"",
        ])
