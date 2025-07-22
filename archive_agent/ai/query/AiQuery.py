#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import hashlib
from typing import List

from pydantic import BaseModel, ConfigDict
from qdrant_client.http.models import ScoredPoint

from archive_agent.util.format import get_point_reference_info

logger = logging.getLogger(__name__)


class AnswerItem(BaseModel):
    answer: str
    chunk_ref_list: List[str]
    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false


class QuerySchema(BaseModel):
    question_rephrased: str
    answer_list: List[AnswerItem]
    answer_conclusion: str
    follow_up_questions_list: List[str]
    is_rejected: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false


class AiQuery:

    @staticmethod
    def get_prompt_query(question: str, context: str) -> str:
        return "\n".join([
            "Act as a query agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to answer the question using only the provided context as source of truth.",
            "Adapt your response to suit any use case: factual lookups, analysis, how-to guides, comparisons, or creative exploration.",
            "Use a neutral, encyclopedic tone like Wikipedia—precise, structured, and comprehensive—",
            "while being engaging and helpful like ChatGPT: conversational, practical, and user-focused.",
            "You must output structured information using the exact response fields described below.",
            "Do not return any explanations, commentary, or additional fields.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `question_rephrased`:",
            "    Rephrase the original question in clear, context-aware language.",
            "    Preserve intent, resolve ambiguities, and frame it neutrally for broad applicability.",
            "",
            "- `answer_list`:",
            "    A list of objects, each containing a detailed, self-contained answer and its corresponding references.",
            "    Each object must have the following fields:",
            "    - `answer`:",
            "        A detailed, self-contained answer based solely on the context.",
            "        It should cover a distinct aspect: start with a clear definition or key fact,",
            "        explain thoroughly with examples or steps, and include practical applications or implications.",
            "        Use light Markdown for emphasis (e.g., **bold**, *italic*),",
            "        but no headings or other hierarchical elements.",
            "        Each answer must not contain bullet points or hierarchy. Each answer must be \"flat\".",
            "        Instead, for bullet points, multiple answers should be added to the answer_list.",
            "        Do NOT start entries with bolded titles or phrases that act as headings (e.g., avoid '- **Topic:**').",
            "        Integrate all content narratively within each entry.",
            "        Keep language engaging and accessible: avoid jargon unless explained, use active voice, and anticipate user needs",
            "        (e.g., \"This means you can...\").",
            "        DO NOT mention references.",
            "        DO NOT indicate which chunk the answer is from.",
            "        DO NOT include citations or provenance of any kind.",
            "        Each entry must stand alone as an informative, complete response.",
            "    - `chunk_ref_list`:",
            "        A list of reference designators indicating which chunks informed this specific answer.",
            "        These MUST follow the exact format as provided in the context: `<<< 0123456789ABCDEF >>>`,",
            "        where `0123456789ABCDEF` is a 16-character hex string.",
            "        DO NOT include any chunk references anywhere else except in this list.",
            "",
            "- `answer_conclusion`:",
            "    A concise, integrative summary synthesizing the main ideas from `answer_list`.",
            "    Highlight connections, key takeaways, and broader implications without introducing new info.",
            "    End with a helpful note if relevant (e.g., \"For further details, consider...\").",
            "",
            "- `follow_up_questions_list`:",
            "    A list of 3-5 specific, well-formed follow-up questions that extend the topic.",
            "    Make them diverse: e.g., seek clarification, explore alternatives, dive deeper, or apply to related scenarios.",
            "    Each must be self-contained—do NOT reference 'the answer', 'the context', or prior responses.",
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
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- DO NOT mention references or chunks in `answer`, `answer_conclusion`, or `follow_up_questions_list`.",
            "- DO NOT cite, explain, or hint at which chunk supports which answer.",
            "- The only place to refer to chunks is the `chunk_ref_list` in each `answer_list` item.",
            "- Ensure responses are versatile: factual queries get objective details; how-to gets step-by-step; analytical gets pros/cons.",
            "- Every field must follow its format exactly. No extra commentary, no schema deviations.",
            "",
            "Context:\n\"\"\"\n" + context + "\n\"\"\"\n\n",
            "Question:\n\"\"\"\n" + question + "\n\"\"\"",
        ])

    @staticmethod
    def get_point_hash(point: ScoredPoint) -> str:
        """
        Get point hash.
        :param point: Point.
        :return: Point hash (16-character hex, SHA-1).
        """
        assert point.payload is not None  # makes pyright happy

        payload = point.payload

        chunk_index = str(payload['chunk_index'])
        chunks_total = str(payload['chunks_total'])
        file_path = str(payload['file_path'])
        file_mtime = str(payload['file_mtime'])

        line_range = str(payload.get('line_range', ''))
        page_range = str(payload.get('page_range', ''))

        point_str = "".join([
            chunk_index,
            chunks_total,
            file_path,
            file_mtime,
            line_range,
            page_range,
        ])

        # noinspection PyTypeChecker
        return hashlib.sha1(point_str.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def get_context_from_points(points: List[ScoredPoint]) -> str:
        """
        Get context from points.
        :param points: Points.
        :return: Context string.
        """
        return "\n\n\n\n".join([
            "\n\n".join([
                f"<<< {AiQuery.get_point_hash(point)} >>>",
                f"{point.payload['chunk_text']}\n",
            ])
            for point in points
            if point.payload is not None  # makes pyright happy
        ])

    @staticmethod
    def format_query_references(query_result: QuerySchema, points: List[ScoredPoint]) -> QuerySchema:
        """
        Format reference designators in query result as human-readable references infos.
        :param query_result: Query result.
        :param points: Points.
        :return: Query result with reference designators formatted as human-readable reference infos.
        """
        # Build a mapping: hash -> ScoredPoint
        points_by_hash = {
            AiQuery.get_point_hash(point): point
            for point in points
            if point.payload is not None
        }

        # Extracts 16-char hash from '<<< 0123456789ABCDEF >>>'
        def extract_hash(ref: str) -> str:
            ref = ref.strip()
            if ref.startswith("<<< ") and ref.endswith(" >>>"):
                core = ref[4:-4].strip()
                # Robustness: only accept exactly 16 hex chars (optional strict check)
                if len(core) == 16 and all(c in "0123456789abcdefABCDEF" for c in core):
                    return core
            # Fallback: just return as-is (should not occur)
            return ref

        for answer in query_result.answer_list:
            for i, chunk_ref in enumerate(answer.chunk_ref_list):
                hash_id = extract_hash(chunk_ref)
                point = points_by_hash.get(hash_id)
                if point is not None:
                    answer.chunk_ref_list[i] = get_point_reference_info(point)
                else:
                    answer.chunk_ref_list[i] = f"??? ({hash_id})"

        return query_result

    @staticmethod
    def get_answer_text(query_result: QuerySchema) -> str:
        """
        Get answer text.
        :param query_result: Query result.
        :return: Formatted answer, or empty string if rejected.
        """
        if query_result.is_rejected:
            return ""

        # Create a list of unique references in order of appearance
        all_refs_ordered = []
        ref_map = {}
        for item in query_result.answer_list:
            for ref in item.chunk_ref_list:
                if ref not in ref_map:
                    ref_map[ref] = len(all_refs_ordered) + 1
                    all_refs_ordered.append(ref)

        answers_formatted = []
        for item in query_result.answer_list:
            ref_markers = ""
            if item.chunk_ref_list:
                # Sort the references by their appearance order for this answer
                sorted_refs = sorted(list(set(item.chunk_ref_list)), key=lambda r: ref_map[r])
                ref_numbers = [ref_map[ref] for ref in sorted_refs]
                ref_markers = " " + " ".join(f"**[{num}]**" for num in ref_numbers)
            answers_formatted.append(f"- {item.answer}{ref_markers}")

        answer_list_text = "\n".join(answers_formatted)

        chunk_ref_list_text = "\n".join([
            f"- **[{i + 1}]** {ref}"
            for i, ref in enumerate(all_refs_ordered)
        ])

        follow_up_questions_list_text = "\n".join([
            f"- {follow_up}"
            for follow_up in query_result.follow_up_questions_list
        ])

        answer_text = "\n\n".join(filter(None, [
            f"### Question",
            f"**{query_result.question_rephrased}**",
            f"### Answers",
            f"{answer_list_text}",
            f"### Conclusion",
            f"**{query_result.answer_conclusion}**",
            f"### References" if chunk_ref_list_text else "",
            chunk_ref_list_text if chunk_ref_list_text else "",
            f"### Follow-Up Questions",
            f"{follow_up_questions_list_text}",
        ]))

        return answer_text
