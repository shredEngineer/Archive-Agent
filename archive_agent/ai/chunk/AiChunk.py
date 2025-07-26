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
    def get_prompt_chunk(line_numbered_text: str, chunk_words_target: int) -> str:
        return "\n".join([
            f"Act as an elite chunking agent for a high-performance semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            f"Your task is to segment the text into semantically optimal chunks, maximizing coherence, entity retention,",
            f"and searchability.",
            f"You must output structured information using the exact response fields described below.",
            f"You must not return any explanations, commentary, or additional fields.",
            "",
            f"RESPONSE FIELDS:",
            "",
            f"- `chunk_start_lines`:",
            f"    List of line numbers. Each marks the start of a chunk. The first value MUST be 1 (the first line).",
            f"    The list must be strictly increasing. No duplicates.",
            "",
            f"- `headers`:",
            f"    List of header strings, one for each chunk, in the same order as `chunk_start_lines`.",
            "",
            f"HEADER RULES:",
            f"- Each header must be absolute, concise, and hyper-specific:",
            f"  a standalone title reflecting the chunk's core semantic essence.",
            f"- Prioritize key entities, relations, or concepts for unmatched RAG search precision.",
            f"- Incorporate initial headings verbatim if present, then enhance with precise, context-rich descriptors.",
            f"- Ban generic placeholders (e.g., 'Section', 'Content'); use title-case phrases with unique, content-driven nouns.",
            f"- Ensure headers are dense with semantic value, supporting advanced query matching.",
            "",
            f"CHUNKING RULES:",
            f"- Analyze the entire text holistically to define chunk boundaries, ensuring each chunk is a self-contained semantic unit.",
            f"- Target chunks around {chunk_words_target} words for deep context, allowing flexibility to exceed this for coherence.",
            f"- Enforce a minimum of {chunk_words_target} words per chunk,",
            f"  permitting smaller sizes only at text end or for critical semantic breaks.",
            f"- Leverage structural cues (e.g., Markdown/HTML headings) to anchor chunks, always pairing headings with subsequent content.",
            f"- Merge short heading-content pairs or multiple sparse sections into the next meaningful block,",
            f"  unless it disrupts topic integrity.",
            f"- Initiate new chunks exclusively at significant semantic shifts, avoiding arbitrary splits.",
            f"- Permit chunks to grow beyond {chunk_words_target} words to preserve topic continuity and entity relationships.",
            f"- For the final segment: Integrate with the prior chunk if under {chunk_words_target}/2 words,",
            f"  unless it compromises meaning.",
            "",
            f"SPECIAL RULES:",
            f"- If text is in square brackets, e.g., [Image description], prefer to keep it intact without breaking across lines.",
            "",
            f"Text with line numbers:",
            f"\"\"\"\n{line_numbered_text}\n\"\"\"",
        ])
