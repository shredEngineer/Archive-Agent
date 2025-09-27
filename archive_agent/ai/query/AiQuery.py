# archive_agent/ai/query/AiQuery.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import hashlib
from logging import Logger
from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict
from qdrant_client.http.models import ScoredPoint

from archive_agent.util.format import get_point_reference_info
from archive_agent.db.QdrantSchema import parse_payload


# === Reference repair configuration (module-level) ===
# Enable/disable soft repair of corrupted 16-char hex reference hashes.
HASH_REPAIR_ENABLED: bool = True
# Maximum allowed Hamming distance for a repair to be accepted.
HASH_REPAIR_MAX_DIST: int = 2
# Hex charset used for validation (lowercase only; inputs are normalized to lowercase).
_HEX_CHARS: str = "0123456789abcdef"


class AnswerItem(BaseModel):
    answer: str
    chunk_ref_list: List[str]
    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS


class QuerySchema(BaseModel):
    """
    This is the format returned by MCP (`#get_answer_rag`) and for JSON output (`--to-json`, `--to-json-auto`).
    """
    question_rephrased: str
    answer_list: List[AnswerItem]
    answer_conclusion: str
    follow_up_questions_list: List[str]
    is_rejected: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS


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
            "RESPONSE STRATEGY (APPLIES TO ALL FIELDS):",
            "- Prefer multi-chunk synthesis over single-chunk paraphrase.",
            "- Consider both central and peripheral (lower-similarity) chunks when they are context-coherent.",
            "- Connect dots across distant parts of the context; favor breadth and integration.",
            "- Target 10–16 `answer_list` items when the context allows; never fewer than 5 unless content is truly sparse.",
            "- Use more references: for each answer, include 2–6 chunk references if available.",
            "- Diversify references across the whole output; aim to cover ≥8 unique chunks overall, if present.",
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
            "        After the evidence-based explanation, optionally append one short sentence labeled",
            "        \"Speculative — What if: ...\" that extrapolates or poses a counterfactual consistent with the context.",
            "        This speculative line must remain coherent with the provided material and must not add external facts.",
            "        DO NOT mention references.",
            "        DO NOT indicate which chunk the answer is from.",
            "        DO NOT include citations or provenance of any kind.",
            "        Each entry must stand alone as an informative, complete response.",
            "    - `chunk_ref_list`:",
            "        A list of reference designators indicating which chunks informed this specific answer.",
            "        These MUST follow the exact format as provided in the context: `<<< 0123456789ABCDEF >>>`,",
            "        where `0123456789ABCDEF` is a 16-character hexadecimal hash string."
            "        The `<<< ` prefix and the ` >>>` suffix are required to delimit the hash in the reference designator.",
            "        Include 2–6 references per answer when possible;",
            "        prefer mixing central and peripheral chunks when they help synthesis.",
            "        DO NOT include any chunk references anywhere else except in this list.",
            "",
            "- `answer_conclusion`:",
            "    A concise, integrative summary synthesizing the main ideas from `answer_list`.",
            "    Highlight connections, key takeaways, and broader implications without introducing new info.",
            "    If fewer than 10 answers were feasible, briefly acknowledge context limitations.",
            "    You may briefly note where speculative \"What if\" ideas converge or diverge, without adding new facts.",
            "",
            "- `follow_up_questions_list`:",
            "    A list of 4-6 specific, well-formed follow-up questions that extend the topic.",
            "    Make them diverse: e.g., seek clarification, explore alternatives, dive deeper, or apply to related scenarios.",
            "    Include at least one explicitly counterfactual or \"What if\" question.",
            "    Each must be self-contained—do NOT reference 'the answer', 'the context', or prior responses.",
            "    Each must stand alone as an informative, complete response.",
            "    **In the question itself include all context required to understand it.**"
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
            "- Aim for comprehensive coverage: prefer returning 10–16 `answer_list` items when context supports it.",
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
        model = parse_payload(point.payload)
        chunk_index = str(model.chunk_index)
        chunks_total = str(model.chunks_total)
        file_path = str(model.file_path)
        file_mtime = str(model.file_mtime)
        line_range = str(model.line_range or '')
        page_range = str(model.page_range or '')

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
                f"{parse_payload(point.payload).chunk_text}\n",
            ])
            for point in points
        ])

    @staticmethod
    def format_query_references(
            logger: Logger,
            query_result: QuerySchema,
            points: List[ScoredPoint],
    ) -> QuerySchema:
        """
        Format reference designators in query result as human-readable reference infos.

        Broken/unresolvable references are **discarded** (not replaced with placeholders)
        and a failure is logged. Soft repairs (Hamming-nearest within the configured
        radius) are attempted when enabled.
        :param logger: Logger.
        :param query_result: Query result.
        :param points: Points.
        :return: Query result with reference designators formatted as human-readable
                 reference infos; invalid references removed.
        """
        # Build a mapping: hash -> ScoredPoint  (store keys lowercase for robustness)
        points_by_hash = {
            AiQuery.get_point_hash(point).lower(): point
            for point in points
            if point.payload is not None
        }

        # Extracts 16-char token from '<<< 0123456789ABCDEF >>>'
        def extract_hash(ref: str) -> str:
            # Let's allow some slack from weaker or overloaded LLMs here...
            hash_str = ref.replace("<<<", "").replace(">>>", "").strip()
            hash_str = hash_str.lower()
            if len(hash_str) == 16 and all(c in _HEX_CHARS for c in hash_str):
                return hash_str
            logger.critical(f"⚠️ Invalid reference format: '{ref}'")
            return hash_str  # Return whatever we found; may be repaired below.

        def hamming_distance(a: str, b: str) -> int:
            """
            Compute the Hamming distance of two equal-length strings.
            Preconditions: len(a) == len(b).
            """
            return sum((ch1 != ch2) for ch1, ch2 in zip(a, b))

        def try_repair_hash(maybe_hash: str, max_dist: int) -> Optional[str]:
            """
            Attempt to repair a corrupted 16-char hash by nearest-neighbor search
            in Hamming space over known point hashes.

            :param maybe_hash: The (possibly corrupted) 16-char token extracted from the reference.
            :param max_dist: Maximum Hamming distance allowed for a repair to be accepted.
            :return: Repaired lowercase hash if confidently matched; otherwise None.
            """
            token = (maybe_hash or "").lower()
            if len(token) != 16:
                return None

            # Exact match — nothing to repair.
            if token in points_by_hash:
                return token

            best: Optional[Tuple[int, str]] = None
            for candidate in points_by_hash.keys():
                dist = hamming_distance(token, candidate)
                if best is None or dist < best[0]:
                    best = (dist, candidate)
                    # Early stopping is intentionally conservative; we keep scanning to avoid ties ambiguity.

            if best is None:
                return None

            dist, winner = best
            if dist <= max_dist:
                logger.warning(
                    f"🔧 Repaired reference hash '{maybe_hash}' -> '{winner}' (Hamming distance={dist})."
                )
                return winner
            return None

        for answer in query_result.answer_list:
            # Build a new list to **discard** broken references instead of emitting '???'.
            formatted_refs: List[str] = []
            for chunk_ref in answer.chunk_ref_list:
                hash_id = extract_hash(chunk_ref)
                point = points_by_hash.get(hash_id.lower())
                if point is not None:
                    formatted_refs.append(
                        get_point_reference_info(logger, point, verbose=False)
                    )
                    continue

                # Attempt a soft repair via Hamming-nearest neighbor within a small radius.
                repaired_hash: Optional[str] = None
                if HASH_REPAIR_ENABLED:
                    repaired_hash = try_repair_hash(hash_id, max_dist=HASH_REPAIR_MAX_DIST)

                if repaired_hash is not None:
                    repaired_point = points_by_hash.get(repaired_hash)
                    if repaired_point is not None:
                        formatted_refs.append(
                            get_point_reference_info(logger, repaired_point, verbose=False)
                        )
                        continue

                # Log and **discard** the unresolved reference token.
                logger.error(f"❌ Unresolvable reference; discarding token '{hash_id}'.")

            # Overwrite with only successfully resolved (or repaired) references.
            answer.chunk_ref_list = formatted_refs

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
