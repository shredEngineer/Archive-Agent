#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import json
import hashlib
from typing import cast, Dict, List

from qdrant_client.http.models import ScoredPoint

from archive_agent.ai.AiResult import AiResult
from archive_agent.ai.AiVisionLogic import AiVisionLogic
from archive_agent.ai_provider.AiProvider import AiProvider

from archive_agent.ai_schema.ChunkSchema import ChunkSchema
from archive_agent.ai_schema.RerankSchema import RerankSchema
from archive_agent.ai_schema.QuerySchema import QuerySchema
from archive_agent.ai_schema.VisionSchema import VisionSchema

from archive_agent.core.CliManager import CliManager
from archive_agent.util.RetryManager import RetryManager
from archive_agent.util.format import get_point_reference_info
from archive_agent.util.text_util import prepend_line_numbers

logger = logging.getLogger(__name__)


class AiManager(RetryManager):
    """
    AI manager.
    """

    @staticmethod
    def get_prompt_vision() -> str:
        return AiVisionLogic.get_prompt_vision()

    @staticmethod
    def format_vision_answer(vision_result: VisionSchema) -> str:
        return AiVisionLogic.format_vision_answer(vision_result)

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
            "RERANKING RULES:",
            "- Consider only the provided chunk texts and the question.",
            "- Assess semantic relevance, not superficial similarity.",
            "- If several chunks are equally relevant, preserve their original order.",
            "",
            "Chunks (JSON array):\n" + indexed_chunks_json_text,
            "",
            "Question:\n\"\"\"\n" + question + "\n\"\"\"",
        ])

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
                f"<<< {AiManager.get_point_hash(point)} >>>",
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
            AiManager.get_point_hash(point): point
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

    def __init__(
            self,
            ai_provider: AiProvider,
            cli: CliManager,
            chunk_lines_block: int,
    ):
        """
        Initialize AI manager.
        :param ai_provider: AI provider.
        :param cli: CLI manager.
        :param chunk_lines_block: Number of lines per block for chunking.
        """
        self.ai_provider = ai_provider

        self.cli = cli

        self.chunk_lines_block = chunk_lines_block

        self.total_tokens_chunk = 0
        self.total_tokens_embed = 0
        self.total_tokens_rerank = 0
        self.total_tokens_query = 0
        self.total_tokens_vision = 0

        RetryManager.__init__(
            self,
            predelay=0,
            delay_min=0,
            delay_max=60,
            backoff_exponent=2,
            retries=10,
        )

        if not self.ai_provider.supports_vision:
            logger.warning(f"Image vision is DISABLED in your current configuration")

    def usage(self) -> None:
        """
        Show usage.
        """
        if any([x > 0 for x in [
            self.total_tokens_chunk, self.total_tokens_embed, self.total_tokens_rerank, self.total_tokens_query, self.total_tokens_vision
        ]]):
            logger.info(
                f"Used AI API token(s): "
                f"({self.total_tokens_chunk}) chunking, "
                f"({self.total_tokens_embed}) embedding, "
                f"({self.total_tokens_rerank}) reranking, "
                f"({self.total_tokens_query}) query, "
                f"({self.total_tokens_vision}) vision"
            )
        else:
            logger.info(f"No AI API tokens used")

    def chunk(self, sentences: List[str], retries: int = 10) -> ChunkSchema:
        """
        Get chunks of sentences.
        :param sentences: Sentences.
        :param retries: Number of retries.
        :return: ChunkSchema.
        """
        line_numbered_text = "\n".join(prepend_line_numbers(sentences))
        prompt = self.get_prompt_chunk(line_numbered_text=line_numbered_text)
        callback = lambda: self.ai_provider.chunk_callback(prompt=prompt)

        for _ in range(retries):
            try:
                result: AiResult = self.cli.format_ai_chunk(callback=lambda: self.retry(callback), line_numbered_text=line_numbered_text)
                self.total_tokens_chunk += result.total_tokens

                if result.parsed_schema is None:
                    raise RuntimeError("No parsed schema returned")

                result.parsed_schema = cast(ChunkSchema, result.parsed_schema)

                if len(result.parsed_schema.chunk_start_lines) == 0:
                    raise RuntimeError(f"Missing chunk start lines: {result.parsed_schema.chunk_start_lines}")

                if len(result.parsed_schema.chunk_start_lines) != len(result.parsed_schema.headers):
                    raise RuntimeError(
                        f"Mismatch: "
                        f"chunk_start_lines[{len(result.parsed_schema.chunk_start_lines)}] != headers[{len(result.parsed_schema.headers)}]"
                    )

                # Let's allow some slack from weaker or overloaded LLMs here...
                if result.parsed_schema.chunk_start_lines[0] != 1:
                    result.parsed_schema.chunk_start_lines.insert(0, 1)
                    result.parsed_schema.headers.insert(0, "")  # Add empty header for first chunk
                    logger.warning(f"Fixed first chunk start lines: {result.parsed_schema.chunk_start_lines} (added empty header)")

                return result.parsed_schema

            except Exception as e:
                logger.exception(f"Chunking error: {e}")
                continue  # Retry

        raise RuntimeError("Failed to recover from chunking errors")

    def embed(self, text: str) -> List[float]:
        """
        Embed text.
        :param text: Text.
        :return: Embedding vector.
        """
        callback = lambda: self.ai_provider.embed_callback(text)

        result: AiResult = self.cli.format_ai_embed(callback=lambda: self.retry(callback), text=text)
        self.total_tokens_embed += result.total_tokens
        assert result.embedding is not None
        return result.embedding

    def rerank(self, question: str, indexed_chunks: Dict[int, str], retries: int = 10) -> RerankSchema:
        """
        Get reranked chunks based on relevance to question.
        :param question: Question.
        :param indexed_chunks: Indexed chunks.
        :param retries: Number of retries.
        :return: RerankSchema.
        """
        indexed_chunks_json_text = json.dumps(indexed_chunks, ensure_ascii=False, indent=2)
        prompt = self.get_prompt_rerank(question=question, indexed_chunks_json_text=indexed_chunks_json_text)
        callback = lambda: self.ai_provider.rerank_callback(prompt=prompt)

        for _ in range(retries):
            try:
                result: AiResult = self.cli.format_ai_rerank(callback=lambda: self.retry(callback), indexed_chunks=indexed_chunks)
                self.total_tokens_rerank += result.total_tokens

                if result.parsed_schema is None:
                    raise RuntimeError("No parsed schema returned")

                result.parsed_schema = cast(RerankSchema, result.parsed_schema)

                reranked = result.parsed_schema.reranked_indices
                expected = list(indexed_chunks.keys())

                if sorted(reranked) != sorted(expected):
                    raise RuntimeError(
                        f"Reranked indices are not a valid permutation of original indices:\n"
                        f"Original: {expected}\n"
                        f"Reranked: {reranked}"
                    )

                return result.parsed_schema

            except Exception as e:
                logger.exception(f"Reranking error: {e}")
                continue  # Retry

        raise RuntimeError("Failed to recover from reranking errors")

    def query(self, question: str, points: List[ScoredPoint]) -> QuerySchema:
        """
        Get answer to question using RAG.
        :param question: Question.
        :param points: Points.
        :return: QuerySchema.
        """
        context = self.get_context_from_points(points)
        prompt = self.get_prompt_query(question=question, context=context)
        callback = lambda: self.ai_provider.query_callback(prompt=prompt)

        result: AiResult = self.cli.format_ai_query(callback=lambda: self.retry(callback), prompt=prompt)
        self.total_tokens_query += result.total_tokens
        assert result.parsed_schema is not None
        query_result = cast(QuerySchema, result.parsed_schema)
        query_result = self.format_query_references(query_result=query_result, points=points)

        if query_result.is_rejected:
            self.ai_provider.cache.pop()  # Immediately remove rejected AI result from cache

        return query_result

    def vision(self, image_base64: str) -> VisionSchema:
        """
        Convert image to text.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: VisionSchema.
        """
        prompt = self.get_prompt_vision()
        callback = lambda: self.ai_provider.vision_callback(prompt=prompt, image_base64=image_base64)

        result: AiResult = self.cli.format_ai_vision(callback=lambda: self.retry(callback))
        self.total_tokens_vision += result.total_tokens
        assert result.parsed_schema is not None
        vision_result = cast(VisionSchema, result.parsed_schema)

        if vision_result.is_rejected:
            self.ai_provider.cache.pop()  # Immediately remove rejected AI result from cache

        return vision_result
