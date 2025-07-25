#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List

from pydantic import BaseModel, ConfigDict


class ChunkSchema(BaseModel):
    chunk_start_lines: List[int]
    headers: List[str]

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false


class AiChunk:

    @staticmethod
    def get_prompt_chunk(line_numbered_text: str) -> str:
        return "\n".join([
            "Act as a chunking agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to segment the text into semantically coherent chunks.",
            "You must output structured information using the exact response fields described below.",
            "You must not return any explanations, commentary, or additional fields.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `chunk_start_lines`:",
            "    List of line numbers. Each marks the start of a chunk. The first value MUST be 1 (the first line).",
            "    The list must be strictly increasing. No duplicates.",
            "",
            "- `headers`:",
            "    List of header strings, one for each chunk, in the same order as `chunk_start_lines`.",
            "",
            "HEADER RULES:",
            "- Each header must be absolute, atomic, and explicit: standalone, concise, and precisely descriptive.",
            "- Summarize the chunk's core topic with key terms for optimal RAG searchability."
            "  Headers may include multiple sentences without line breaks.",
            "- If a chunk starts with a heading, incorporate it exactly but enhance for clarity and specificity.",
            "- Avoid generic terms like 'Detailed', 'Overview', 'Descriptions';"
            "  use explicit nouns and concepts tied to the chunk's content.",
            "- Use title-case phrases that capture unique semantic value."
            "  Reflect key entities or relations for chunks with entity/relation data.",
            "",
            "CHUNKING RULES:",
            "- Review the entire text before deciding chunk boundaries. Each chunk MUST be semantically coherent.",
            "- Each chunk SHOULD be about 100 words. Chunks must NOT be shorter than 10 lines or 100 words unless strictly necessary.",
            "- Exception: allow smaller chunks at the end of the text or if coherence cannot be maintained otherwise.",
            "- Detect structure (e.g., Markdown headings). Headings must not be a chunk alone; always group with following content.",
            "- If a heading and its content are too short, merge with the next section unless this breaks semantic coherence.",
            "- If multiple headings have little content, group them with the next non-heading content.",
            "- Only create a new chunk at clear semantic or topic boundaries. Do not chunk line by line.",
            "- Make all chunking decisions after reviewing the entire text. Allow chunks to exceed target size to maintain coherence.",
            "- At the end: If the final content is too short, merge with the previous chunk unless this breaks semantic coherence.",
            "",
            "Text with line numbers:",
            "\"\"\"\n" + line_numbered_text + "\n\"\"\"",
        ])
