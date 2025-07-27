#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List

from pydantic import BaseModel, ConfigDict


class RerankSchema(BaseModel):
    reranked_indices: List[int]
    is_rejected: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS


class AiRerank:
    #  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
    #  This file is part of Archive Agent. See LICENSE for details.

    @staticmethod
    def get_prompt_rerank(question: str, indexed_chunks_json_text: str) -> str:
        return "\n".join([
            "Act as a reranking agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to assess the semantic relevance of each chunk to the question.",
            "You are given a list of text chunks as a JSON array, where each array index corresponds to the chunk index.",
            "You must output a JSON object with the exact fields described below.",
            "Do not return any explanations, commentary, or additional fields. Output only the JSON.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `reranked_indices`:",
            "    A list of integer indices.",
            "    If `is_rejected` is false, this list MUST include ALL indices from 0 to (number of chunks - 1) exactly once,",
            "    sorted by descending relevance (most relevant first).",
            "    Do not omit any indices; include even low-relevance ones at the end. Omitting indices will cause errors.",
            "    If `is_rejected` is true, this must be an empty list [].",
            "",
            "- `is_rejected`:",
            "    A Boolean flag. Set to true ONLY if NONE of the chunks contain ANY relevant information to the question",
            "    (e.g., all chunks are completely unrelated to the question's topic, or the list is empty).",
            "    A chunk is relevant if it provides any information that directly helps answer the question or offers useful context.",
            "    If at least one chunk has any degree of relevance (even partial),",
            "    set to false and include ALL indices in reranked_indices, sorted by relevance.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Include this ONLY if `is_rejected` is true. If `is_rejected` is false, set to empty string ''.",
            "    Examples: 'All chunks are entirely unrelated to the question', 'Chunk list is empty',",
            "    'No relevant content in any chunk'.",
            "",
            "RERANKING RULES:",
            "- Consider only the provided chunk texts and the question.",
            "- Assess semantic relevance, not superficial similarity. Relevance means the chunk helps in answering the question.",
            "- If several chunks are equally relevant, preserve their original order.",
            "- IMPORTANT: Never return a partial list of indices when is_rejected is false. Always include all or none.",
            "",
            "EXAMPLE 1 (no relevant chunks):",
            "{\"reranked_indices\": [], \"is_rejected\": true, \"rejection_reason\": \"All chunks are unrelated to the question\"}",
            "",
            "EXAMPLE 2 (some relevant chunks):",
            "{\"reranked_indices\": [2, 0, 1], \"is_rejected\": false, \"rejection_reason\": \"\"}",
            "",
            "Chunks (JSON array):\n" + indexed_chunks_json_text,
            "",
            "Question:\n\"\"\"\n" + question + "\n\"\"\"",
        ])
