#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class RerankSchema(BaseModel):
    reranked_indices: List[int]
    is_rejected: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false


class AiRerank:

    @staticmethod
    def get_prompt_rerank(question: str, indexed_chunks_json_text: str) -> str:
        return "\n".join([
            "Act as a reranking agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to assess the semantic relevance of each chunk to the question.",
            "You are given a list of text chunks as a JSON array, where each array index corresponds to the chunk index.",
            "You must output structured information using the exact response fields described below.",
            "Do not return any explanations, commentary, or additional fields.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `reranked_indices`:",
            "    A list of integer indices, sorted by descending relevance (most relevant first).",
            "    The list must contain each index exactly once.",
            "",
            "- `is_rejected`:",
            "    A Boolean flag. Set `is_rejected: true` ONLY if the context has zero relevant information",
            "    (e.g., completely unrelated or empty).",
            "    If partially relevant, provide answers based on what's available and note limitations in `answer_conclusion`.",
            "    If `is_rejected` is true, leave all other fields blank except `rejection_reason`.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Required ONLY if `is_rejected` is `true`. Leave this field blank if `is_rejected` is `false`.",
            "    Examples: 'context is entirely unrelated to query', 'context is empty', 'no answerable content despite partial matches'.",
            "",
            "RERANKING RULES:",
            "- Consider only the provided chunk texts and the question.",
            "- Assess semantic relevance, not superficial similarity.",
            "- If several chunks are equally relevant, preserve their original order.",
            "",
            "Chunks (JSON array):\n" + indexed_chunks_json_text,
            "",
            "Question:\n\"\"\"\n" + question + "\n\"\"\"",
        ])
