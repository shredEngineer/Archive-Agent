#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import json
from typing import cast, Dict, List, Optional

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

logger = logging.getLogger(__name__)


class AiManager(RetryManager):
    """
    AI manager.
    """

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

        # NOTE: This switches between `AiVisionEntity` and `AiVisionOCR` modules
        # TODO: Use enum instead of 'entity' and 'ocr' literals
        self.requested: Optional[str] = None

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
        prompt = AiChunk.get_prompt_chunk(line_numbered_text=line_numbered_text)
        callback = lambda: self.ai_provider.chunk_callback(prompt=prompt)

        for _ in range(retries):
            try:
                result: AiResult = self.cli.format_ai_chunk(callback=lambda: self.retry(callback), line_numbered_text=line_numbered_text)
                self.total_tokens_chunk += result.total_tokens

                if result.parsed_schema is None:
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    raise RuntimeError("No parsed schema returned")

                result.parsed_schema = cast(ChunkSchema, result.parsed_schema)

                # TODO: Use schema with [start_line, header] items instead of separate lists
                if len(result.parsed_schema.chunk_start_lines) != len(result.parsed_schema.headers):
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    raise RuntimeError(
                        f"Mismatch: "
                        f"chunk_start_lines[{len(result.parsed_schema.chunk_start_lines)}] != headers[{len(result.parsed_schema.headers)}]"
                    )

                if len(result.parsed_schema.chunk_start_lines) == 0:
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    raise RuntimeError(f"Missing chunk start lines: {result.parsed_schema.chunk_start_lines}")

                if result.parsed_schema.chunk_start_lines[0] != 1:
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    raise RuntimeError(f"First chunk must start at line 1: {result.parsed_schema.chunk_start_lines}")

                if not 0 < any(result.parsed_schema.chunk_start_lines) <= len(sentences):
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    raise RuntimeError(f"Invalid line numbers: {result.parsed_schema.chunk_start_lines}")

                return result.parsed_schema

            except Exception as e:
                logger.exception(f"Chunking error: {e}")
                continue  # Retry

        self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
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
        prompt = AiRerank.get_prompt_rerank(question=question, indexed_chunks_json_text=indexed_chunks_json_text)
        callback = lambda: self.ai_provider.rerank_callback(prompt=prompt)

        for _ in range(retries):
            try:
                result: AiResult = self.cli.format_ai_rerank(callback=lambda: self.retry(callback), indexed_chunks=indexed_chunks)
                self.total_tokens_rerank += result.total_tokens

                if result.parsed_schema is None:
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    raise RuntimeError("No parsed schema returned")

                rerank_result = cast(RerankSchema, result.parsed_schema)

                ai_is_stupid = rerank_result.reranked_indices == [0]  # Let's allow some slack from weaker or overloaded LLMs here...
                if rerank_result.is_rejected or ai_is_stupid:
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    logger.critical(f"⚠️  Reranking context rejected: \"{rerank_result.rejection_reason}\"")
                    return rerank_result

                reranked = rerank_result.reranked_indices
                expected = list(indexed_chunks.keys())

                if sorted(reranked) != sorted(expected):
                    self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
                    raise RuntimeError(
                        f"Reranked indices are not a valid permutation of original indices:\n"
                        f"Original: {expected}\n"
                        f"Reranked: {reranked}"
                    )

                return rerank_result

            except Exception as e:
                logger.exception(f"Reranking error: {e}")
                continue  # Retry

        self.ai_provider.cache.pop()  # REMOVE bad AI result from cache
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
        self.total_tokens_query += result.total_tokens
        assert result.parsed_schema is not None
        query_result = cast(QuerySchema, result.parsed_schema)
        query_result = AiQuery.format_query_references(query_result=query_result, points=points)

        if query_result.is_rejected:
            self.ai_provider.cache.pop()  # REMOVE bad AI result from cache

        return query_result

    def vision(self, image_base64: str) -> VisionSchema:
        """
        Convert image to text.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: VisionSchema.
        """
        if self.requested == 'entity':
            prompt = AiVisionEntity.get_prompt_vision()
        elif self.requested == 'ocr':
            prompt = AiVisionOCR.get_prompt_vision()
        else:
            logger.critical("BUG DETECTED: Unrequested call to `AiManager.vision()` — falling back to OCR")
            prompt = AiVisionOCR.get_prompt_vision()

        self.requested = None

        callback = lambda: self.ai_provider.vision_callback(prompt=prompt, image_base64=image_base64)

        result: AiResult = self.cli.format_ai_vision(callback=lambda: self.retry(callback))
        self.total_tokens_vision += result.total_tokens
        assert result.parsed_schema is not None
        vision_result = cast(VisionSchema, result.parsed_schema)

        if vision_result.is_rejected:
            self.ai_provider.cache.pop()  # REMOVE bad AI result from cache

        return vision_result

    def request_entity(self):
        self.requested = 'entity'

    def request_ocr(self):
        self.requested = 'ocr'
