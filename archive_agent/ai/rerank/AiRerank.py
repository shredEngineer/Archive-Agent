#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List, Tuple

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

    @staticmethod
    def validate_permutation(original: List[int], reranked: List[int]) -> Tuple[bool, List[int], List[int], List[int]]:
        """
        Validate that *reranked* is a permutation of *original*.

        :param original: Original index list.
        :param reranked: Proposed reranked index list.
        :returns: Tuple (is_valid, missing, extra, out_of_range)
                  where:
                    - is_valid: True iff sorted(original) == sorted(reranked)
                    - missing: elements in original but not in reranked
                    - extra:   elements in reranked but not in original
                    - out_of_range: elements in reranked not in the closed interval [min(original), max(original)]
        """
        original_set = set(original)
        reranked_set = set(reranked)

        missing = sorted(original_set - reranked_set)
        extra = sorted(reranked_set - original_set)

        if original:
            lo, hi = min(original), max(original)
            out_of_range = sorted([i for i in reranked if (i < lo or i > hi)])
        else:
            out_of_range = []

        is_valid = (not missing) and (not extra) and (not out_of_range) and (len(reranked) == len(original))
        return is_valid, missing, extra, out_of_range

    @staticmethod
    def repair_permutation(original: List[int], reranked: List[int]) -> List[int]:
        """
        Attempt to repair a non-permutation rerank result into a valid permutation.

        Strategy
        --------
        1) Drop out-of-range indices and duplicates while preserving first occurrence order.
        2) Remove any indices not present in *original*.
        3) Append all *missing* indices (those in *original* but missing from *reranked*)
           in the order they appear in *original*.

        This keeps the LLM's preference ordering as much as possible while ensuring a
        correct permutation of *original*.

        :param original: Original index list.
        :param reranked: Proposed reranked index list.
        :returns: A repaired list that is guaranteed to be a permutation of *original*,
                  provided *original* itself is a set-like list of unique ints.
        """
        original_set = set(original)
        seen: set[int] = set()
        lo, hi = (min(original), max(original)) if original else (0, -1)

        # 1) Drop out-of-range & duplicates; 2) remove items not in original
        filtered: List[int] = []
        for i in reranked:
            if i not in original_set:
                continue
            if i < lo or i > hi:
                continue
            if i in seen:
                continue
            seen.add(i)
            filtered.append(i)

        # 3) Append missing indices in original order
        missing_tail = [i for i in original if i not in seen]
        return filtered + missing_tail
