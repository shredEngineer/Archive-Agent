#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List

from pydantic import BaseModel, ConfigDict


class ChunkItem(BaseModel):
    start_line: int
    header: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS


class ChunkSchema(BaseModel):
    chunk_items: List[ChunkItem]

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS

    def get_chunk_start_lines(self):
        return [chunk_item.start_line for chunk_item in self.chunk_items]

    def get_chunk_headers(self):
        return [chunk_item.header for chunk_item in self.chunk_items]


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
            f"- `chunk_items`:",
            f"    List of chunk items. Each item is an object with:",
            f"    - `start_line`: The line number marking the start of the chunk.",
            f"    - `header`: The header string for that chunk.",
            f"    The first `start_line` MUST be 1 (the first line).",
            f"    The `start_line` values must be strictly increasing. No duplicates.",
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
            f"- Strictly target chunks of approximately {chunk_words_target} words,",
            f"  aiming to keep most chunks between {int(chunk_words_target * 0.75)} and {int(chunk_words_target * 1.25)} words",
            f"  for optimal balance between context and granularity.",
            f"- Enforce a soft maximum of {int(chunk_words_target * 1.5)} words per chunk;",
            f"  split larger coherent units if necessary at minor semantic shifts to avoid oversized chunks.",
            f"- Permit smaller chunks only if under {int(chunk_words_target / 2)} words at the text end",
            f"  or for isolated critical semantic units like equations or definitions.",
            f"- Leverage structural cues (e.g., Markdown/HTML headings, subsections, paragraphs, or equation blocks) to anchor chunks,",
            f"  always pairing headings with subsequent content.",
            f"- Aggressively identify and split at semantic shifts, such as changes in topic, new calculations,",
            f"  or transitions between reviews and new analyses, even within sections, to create more chunks.",
            f"- Merge short heading-content pairs or sparse sections only if the result stays under the target word count;",
            f"  otherwise, keep separate or attach to adjacent chunks without exceeding limits.",
            f"- Initiate new chunks at every significant semantic shift, including subsection starts, new derivations,",
            f"  or shifts in frame of reference, avoiding arbitrary splits but prioritizing granularity.",
            f"- For the final segment: Integrate with the prior chunk only if under {int(chunk_words_target / 2)} words",
            f"  and it doesn't exceed the soft maximum; otherwise, create a separate chunk.",
            "",
            f"SPECIAL RULES:",
            f"- If text is in square brackets, e.g., [Image description], prefer to keep it intact without breaking across lines.",
            "",
            f"Text with line numbers:",
            f"\"\"\"\n{line_numbered_text}\n\"\"\"",
        ])
