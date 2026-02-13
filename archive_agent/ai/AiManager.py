#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
from enum import Enum
from typing import cast, Dict, List, Optional

import typer
from openai import BadRequestError
from qdrant_client.http.models import ScoredPoint

from archive_agent.ai.AiResult import AiResult
from archive_agent.ai.chunk.AiChunk import AiChunk, ChunkSchema
from archive_agent.ai.query.AiQuery import AiQuery, QuerySchema
from archive_agent.ai.rerank.AiRerank import AiRerank, RerankSchema
from archive_agent.ai.vision.AiVisionEntity import AiVisionEntity
from archive_agent.ai.vision.AiVisionOCR import AiVisionOCR
from archive_agent.ai.vision.AiVisionSchema import VisionSchema
from archive_agent.ai_provider.AiProvider import AiProvider

from archive_agent.core.CliManager import CliManager
from archive_agent.util.RetryManager import RetryManager
from archive_agent.util.text_util import prepend_line_numbers


class AiVisionRequest(Enum):
    ENTITY = 'entity'
    OCR = 'ocr'


class AiManager(RetryManager):
    """
    AI manager.
    """

    AI_RETRY_KWARGS = {
        'predelay': 0.0,
        'delay_min': 0.0,
        'delay_max': 60.0,
        'backoff_exponent': 2.0,
        'retries': 10,
    }

    SCHEMA_RETRY_ATTEMPTS = 10
    EMBED_TRUNCATION_ATTEMPTS = 10

    def __init__(
            self,
            cli: CliManager,
            chunk_lines_block: int,
            chunk_words_target: int,
            ai_provider: AiProvider,
    ):
        """
        Initialize AI manager.
        :param cli: CLI manager.
        :param chunk_lines_block: Number of lines per block for chunking.
        :param chunk_words_target: Target number of words per chunk.
        :param ai_provider: AI provider.
        """
        self.cli = cli

        self.chunk_lines_block = chunk_lines_block
        self.chunk_words_target = chunk_words_target

        self.ai_provider = ai_provider

        self.ai_usage_stats = {
            "chunk": 0,
            "embed": 0,
            "rerank": 0,
            "query": 0,
            "vision": 0
        }

        # NOTE: This switches between `AiVisionEntity` and `AiVisionOCR` modules
        self.requested: Optional[AiVisionRequest] = None

        RetryManager.__init__(self, **AiManager.AI_RETRY_KWARGS)

        if not self.ai_provider.supports_vision:
            self.cli.logger.warning(f"Image vision is DISABLED in your current configuration")

    def usage(self):
        """
        Show AI token usage.
        """
        if any(self.ai_usage_stats.values()):
            self.cli.logger.info(
                f"Used AI API token(s): "
                f"({self.ai_usage_stats['chunk']}) chunking, "
                f"({self.ai_usage_stats['embed']}) embedding, "
                f"({self.ai_usage_stats['rerank']}) reranking, "
                f"({self.ai_usage_stats['query']}) query, "
                f"({self.ai_usage_stats['vision']}) vision"
            )
        else:
            self.cli.logger.info(f"No AI API tokens used")

    def chunk(self, sentences: List[str]) -> ChunkSchema:
        """
        Get chunks of sentences.
        :param sentences: Sentences.
        :return: ChunkSchema.
        """
        line_numbered_text = "\n".join(prepend_line_numbers(sentences))
        prompt = AiChunk.get_prompt_chunk(line_numbered_text=line_numbered_text, chunk_words_target=self.chunk_words_target)
        callback = lambda: self.ai_provider.chunk_callback(prompt=prompt)

        for _ in range(AiManager.SCHEMA_RETRY_ATTEMPTS):
            try:
                result: AiResult = self.cli.format_ai_chunk(callback=lambda: self.retry(callback), line_numbered_text=line_numbered_text)
                self.ai_usage_stats['chunk'] += result.total_tokens

                if result.parsed_schema is None:
                    self.ai_provider.invalidate_last_cached()
                    raise RuntimeError("No parsed schema returned")

                chunk_result = cast(ChunkSchema, result.parsed_schema)
                chunk_start_lines = chunk_result.get_chunk_start_lines()
                chunk_headers = chunk_result.get_chunk_headers()

                if len(chunk_start_lines) != len(chunk_headers):
                    self.ai_provider.invalidate_last_cached()
                    raise RuntimeError(
                        f"Mismatch: "
                        f"chunk_start_lines[{len(chunk_start_lines)}] != headers[{len(chunk_headers)}]"
                    )

                if len(chunk_start_lines) == 0:
                    self.ai_provider.invalidate_last_cached()
                    raise RuntimeError(f"Missing chunk start lines: {chunk_start_lines}")

                if chunk_start_lines[0] != 1:
                    self.ai_provider.invalidate_last_cached()
                    raise RuntimeError(f"First chunk must start at line 1: {chunk_start_lines}")

                if not 0 < any(chunk_start_lines) <= len(sentences):
                    self.ai_provider.invalidate_last_cached()
                    raise RuntimeError(f"Invalid line numbers: {chunk_start_lines}")

                return chunk_result

            except typer.Exit:
                raise  # Network retries exhausted — don't swallow process exit
            except Exception as e:
                self.cli.logger.exception(f"Chunking error: {e}")
                continue  # Retry

        self.ai_provider.invalidate_last_cached()
        raise RuntimeError("Failed to recover from chunking errors")

    def embed(self, text: str) -> List[float]:
        """
        Embed text.
        :param text: Text.
        :return: Embedding vector.
        """
        original_text = text
        original_word_count = len(text.split())

        for truncation_attempt in range(AiManager.EMBED_TRUNCATION_ATTEMPTS + 1):
            callback = lambda: self.ai_provider.embed_callback(text)

            try:
                result: AiResult = self.cli.format_ai_embed(callback=lambda: self.retry(callback), text=text)
                self.ai_usage_stats['embed'] += result.total_tokens
                assert result.embedding is not None
                return result.embedding
            except BadRequestError as e:
                error_body = getattr(e, 'body', {})
                error_message = error_body.get('message', '') if isinstance(error_body, dict) else str(e)

                # Check for token limit error (rare case: chunk exceeds embedding model token limit)
                if "maximum context length" in error_message and truncation_attempt < AiManager.EMBED_TRUNCATION_ATTEMPTS:
                    # Progressive truncation: 10% per attempt (last resort for oversized chunks)
                    truncation_percent = (truncation_attempt + 1) * 10
                    keep_percent = 100 - truncation_percent

                    # Truncate by words
                    words = original_text.split()
                    truncated_word_count = int(len(words) * keep_percent / 100)
                    text = " ".join(words[:truncated_word_count])

                    self.cli.logger.warning(
                        f"⚠️ Chunk exceeded embedding token limit (truncation attempt {truncation_attempt + 1}). "
                        f"Truncating {truncation_percent}% ({original_word_count} → {truncated_word_count} words) and retrying... "
                        f"Please check your config to avoid this error."
                    )
                    continue  # Retry with truncated text

                # Re-raise if not a token limit error or max attempts reached
                raise

        raise RuntimeError(f"Failed to embed after {AiManager.EMBED_TRUNCATION_ATTEMPTS} truncation attempts")

    def rerank(self, question: str, indexed_chunks: Dict[int, str]) -> RerankSchema:
        """
        Get reranked chunks based on relevance to question.
        :param question: Question.
        :param indexed_chunks: Indexed chunks.
        :return: RerankSchema.
        """
        indexed_chunks_json_text = json.dumps(indexed_chunks, ensure_ascii=False, indent=2)
        prompt = AiRerank.get_prompt_rerank(question=question, indexed_chunks_json_text=indexed_chunks_json_text)
        callback = lambda: self.ai_provider.rerank_callback(prompt=prompt)

        for _ in range(AiManager.SCHEMA_RETRY_ATTEMPTS):
            try:
                result: AiResult = self.cli.format_ai_rerank(callback=lambda: self.retry(callback), indexed_chunks=indexed_chunks)
                self.ai_usage_stats['rerank'] += result.total_tokens

                if result.parsed_schema is None:
                    self.ai_provider.invalidate_last_cached()
                    raise RuntimeError("No parsed schema returned")

                rerank_result = cast(RerankSchema, result.parsed_schema)

                ai_is_stupid = rerank_result.reranked_indices == [0]  # Let's allow some slack from weaker or overloaded LLMs here...
                if rerank_result.is_rejected or ai_is_stupid:
                    self.ai_provider.invalidate_last_cached()
                    self.cli.logger.critical(f"⚠️ Reranking context rejected: \"{rerank_result.rejection_reason}\"")
                    return rerank_result

                reranked = rerank_result.reranked_indices
                expected = list(indexed_chunks.keys())

                # First, validate strictly
                is_valid, missing, extra, oob = AiRerank.validate_permutation(expected, reranked)
                if not is_valid:
                    self.ai_provider.invalidate_last_cached()

                    # Auto-repair path for production solidity
                    repaired = AiRerank.repair_permutation(expected, reranked)

                    # Validate again to be absolutely sure
                    is_valid2, missing2, extra2, oob2 = AiRerank.validate_permutation(expected, repaired)
                    if not is_valid2:
                        raise RuntimeError(
                            "Reranked indices could not be repaired into a valid permutation:\n"
                            f"Original: {expected}\n"
                            f"Reranked: {reranked}\n"
                            f"Missing: {missing} | Extra: {extra} | Out-of-range: {oob}\n"
                            f"Repair missing: {missing2} | Repair extra: {extra2} | Repair out-of-range: {oob2}"
                        )

                    # Log the discrepancy and proceed with repaired indices
                    self.cli.logger.warning(
                        "⚠️ Auto-repaired invalid rerank permutation.\n"
                        f"Original: {expected}\n"
                        f"Received: {reranked}\n"
                        f"Repaired: {repaired}\n"
                        f"Missing: {missing} | Extra: {extra} | Out-of-range: {oob}"
                    )
                    # Mutate the schema in-place so downstream users see the corrected order.
                    rerank_result.reranked_indices = repaired

                return rerank_result

            except typer.Exit:
                raise  # Network retries exhausted — don't swallow process exit
            except Exception as e:
                self.cli.logger.exception(f"Reranking error: {e}")
                continue  # Retry

        self.ai_provider.invalidate_last_cached()
        raise RuntimeError("Failed to recover from reranking errors")

    def query(self, question: str, points: List[ScoredPoint]) -> QuerySchema:
        """
        Get answer to question using RAG.
        :param question: Question.
        :param points: Points.
        :return: QuerySchema.
        """
        context = AiQuery.get_context_from_points(points)
        prompt = AiQuery.get_prompt_query(question=question, context=context)
        callback = lambda: self.ai_provider.query_callback(prompt=prompt)

        result: AiResult = self.cli.format_ai_query(callback=lambda: self.retry(callback), prompt=prompt)
        self.ai_usage_stats['query'] += result.total_tokens
        assert result.parsed_schema is not None
        query_result = cast(QuerySchema, result.parsed_schema)
        query_result = AiQuery.format_query_references(logger=self.cli.logger, query_result=query_result, points=points)

        if query_result.is_rejected:
            self.ai_provider.invalidate_last_cached()

        return query_result

    def vision(self, image_base64: str) -> VisionSchema:
        """
        Convert image to text.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: VisionSchema.
        """
        if self.requested == AiVisionRequest.ENTITY:
            prompt = AiVisionEntity.get_prompt_vision()
        elif self.requested == AiVisionRequest.OCR:
            prompt = AiVisionOCR.get_prompt_vision()
        else:
            self.cli.logger.critical("⚠️ BUG DETECTED: Unrequested call to `AiManager.vision()` — falling back to OCR")
            prompt = AiVisionOCR.get_prompt_vision()

        self.requested = None

        callback = lambda: self.ai_provider.vision_callback(prompt=prompt, image_base64=image_base64)

        result: AiResult = self.cli.format_ai_vision(callback=lambda: self.retry(callback))
        self.ai_usage_stats['vision'] += result.total_tokens
        assert result.parsed_schema is not None
        vision_result = cast(VisionSchema, result.parsed_schema)

        if vision_result.is_rejected:
            self.ai_provider.invalidate_last_cached()

        return vision_result

    def request_entity(self):
        self.requested = AiVisionRequest.ENTITY

    def request_ocr(self):
        self.requested = AiVisionRequest.OCR
