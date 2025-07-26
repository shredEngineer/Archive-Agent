# TODO: Move `format_ai_chunk` to `AiChunk` etc.

#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
import logging
from typing import Callable, List, Dict, cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from qdrant_client.models import ScoredPoint

from archive_agent.ai.AiResult import AiResult

from archive_agent.ai.query.AiQuery import QuerySchema
from archive_agent.ai.vision.AiVisionSchema import VisionSchema

from archive_agent.util.format import format_chunk_brief, get_point_reference_info


class CliManager:
    """
    CLI manager.
    """

    VERBOSE_CHUNK: bool = False  # enabled by --verbose flag
    VERBOSE_RERANK: bool = False  # enabled by --verbose flag
    VERBOSE_EMBED: bool = False  # enabled by --verbose flag
    VERBOSE_QUERY: bool = False  # enabled by --verbose flag
    VERBOSE_VISION: bool = False  # enabled by --verbose flag
    VERBOSE_RETRIEVAL: bool = False  # enabled by --verbose flag
    VERBOSE_USAGE: bool = True

    def __init__(self, verbose: bool = False):
        """
        Initialize CLI manager.
        :param verbose: Verbosity switch.
        """
        CliManager.VERBOSE_CHUNK = verbose
        CliManager.VERBOSE_RERANK = verbose
        CliManager.VERBOSE_EMBED = verbose
        CliManager.VERBOSE_QUERY = verbose
        CliManager.VERBOSE_VISION = verbose
        CliManager.VERBOSE_RETRIEVAL = verbose

        self.logger = logging.getLogger(__name__)

        self.console = Console(markup=False)

    def format_json(self, text: str) -> None:
        """
        Format text as JSON.
        :param text: Text.
        """
        try:
            data = json.loads(text)
            pretty = Pretty(data, expand_all=True)
            self.console.print(Panel(pretty, title="Structured output", style="blue", border_style="blue"))
        except json.JSONDecodeError:
            self.console.print(Panel(f"{text}", title="Raw output", style="red", border_style="red"))

    def prompt(self, message: str, is_cmd: bool, **kwargs) -> str:
        """
        Prompt user with message.
        :param message: Message.
        :param is_cmd: Enables "> " command style prompt.
        :param kwargs: Additional arguments for typer.prompt.
        :return: User input.
        """
        if is_cmd:
            self.logger.info(f"⚡ Archive Agent: {message}")
            return typer.prompt("", prompt_suffix="> ", **kwargs)
        else:
            self.logger.info(f"⚡ Archive Agent")
            return typer.prompt(message, prompt_suffix="", **kwargs)

    def format_ai_chunk(
            self,
            callback: Callable[[], AiResult],
            line_numbered_text: str,
    ) -> AiResult:
        """
        Format text to be chunked and AI result of chunk callback.
        :param callback: Chunk callback returning AI result.
        :param line_numbered_text: Text with line numbers.
        :return: AI result.
        """
        self.logger.info(f"Chunking...")

        if CliManager.VERBOSE_CHUNK:
            self.console.print(Panel(f"{line_numbered_text}", title="Text", style="blue", border_style="blue"))

        self.logger.info("⌛ Awaiting AI chunking…")

        result: AiResult = callback()

        if CliManager.VERBOSE_USAGE:
            self.logger.info(f"Used ({result.total_tokens}) AI API token(s) for chunking")

        if CliManager.VERBOSE_CHUNK:
            self.format_json(result.output_text)

        return result

    def format_ai_rerank(
            self,
            callback: Callable[[], AiResult],
            indexed_chunks: Dict[int, str],
    ) -> AiResult:
        """
        Format chunks to be reranked and AI result of rerank callback.
        :param callback: Rerank callback returning AI result.
        :param indexed_chunks: Indexed chunks.
        :return: AI result.
        """
        if CliManager.VERBOSE_RERANK:
            indexed_chunks_str = "\n".join([
                f"{index:>3} : {format_chunk_brief(chunk=chunk)}"
                for index, chunk in indexed_chunks.items()
            ])
            self.console.print(Panel(f"{indexed_chunks_str}", title="Indexed Chunks", style="blue", border_style="blue"))

        self.logger.info("⌛ Awaiting AI reranking…")

        result: AiResult = callback()

        if CliManager.VERBOSE_USAGE:
            self.logger.info(f"Used ({result.total_tokens}) AI API token(s) for reranking")

        if CliManager.VERBOSE_RERANK:
            self.format_json(result.output_text)

        return result

    def format_ai_embed(
            self,
            callback: Callable[[], AiResult],
            text: str,
    ) -> AiResult:
        """
        Format text to be embedded.
        :param callback: Embed callback returning AI result.
        :param text: Text.
        :return: AI result.
        """
        if CliManager.VERBOSE_EMBED:
            self.format_chunk(text)

        self.logger.info("⌛ Awaiting AI embedding…")

        result: AiResult = callback()

        if CliManager.VERBOSE_USAGE:
            self.logger.info(f"Used ({result.total_tokens}) AI API token(s) for embedding")

        return result

    def format_ai_query(
            self,
            callback: Callable[[], AiResult],
            prompt: str,
    ) -> AiResult:
        """
        Format prompt and AI result of query callback.
        :param callback: Query callback returning AI result.
        :param prompt: Prompt.
        :return: AI result.
        """
        if CliManager.VERBOSE_QUERY:
            self.console.print(Panel(f"{prompt}", title="Query", style="magenta", border_style="magenta"))

        self.logger.info("⌛ Awaiting AI response…")

        result: AiResult = callback()

        if CliManager.VERBOSE_USAGE:
            self.logger.info(f"Used ({result.total_tokens}) AI API token(s) for query")

        if CliManager.VERBOSE_QUERY:
            self.format_json(result.output_text)

        return result

    def format_ai_vision(
            self,
            callback: Callable[[], AiResult],
    ) -> AiResult:
        """
        Format AI result of vision callback.
        :param callback: Vision callback returning AI result.
        :return: AI result.
        """
        self.logger.info("⌛ Awaiting AI vision…")

        result: AiResult = callback()

        if CliManager.VERBOSE_VISION:
            vision_result = cast(VisionSchema, result.parsed_schema)
            if vision_result.is_rejected:
                self.console.print(
                    Panel(
                        f"{vision_result.rejection_reason}",
                        title="Vision rejected",
                        style="red",
                        border_style="red"
                    )
                )
            else:
                self.format_json(result.output_text)

        if CliManager.VERBOSE_USAGE:
            self.logger.info(f"Used ({result.total_tokens}) AI API token(s) for vision")

        return result

    def format_point(self, point: ScoredPoint) -> None:
        """
        Format point.
        :param point: Point.
        """
        self.logger.info(f"({point.score * 100:>6.2f} %) match: {get_point_reference_info(point)}")

    def format_retrieved_points(self, points: List[ScoredPoint]) -> None:
        """
        Format chunks of retrieved points.
        :param points: Retrieved points.
        """
        if len(points) == 0:
            self.logger.info(f"⚠️  No retrieved results")
            return

        self.logger.info(f"✅  Retrieved ({len(points)}) chunk(s):")

        for point in points:

            assert point.payload is not None

            self.format_point(point)

            if CliManager.VERBOSE_RETRIEVAL:
                self.format_chunk(point.payload['chunk_text'])

    def format_reranked_points(self, points: List[ScoredPoint]) -> None:
        """
        Format chunks of reranked points.
        :param points: Reranked points.
        """
        if len(points) == 0:
            self.logger.info(f"⚠️  No reranked results")
            return

        self.logger.info(f"✅  Reranked and limited down to ({len(points)}) chunk(s):")

        for point in points:

            assert point.payload is not None

            self.format_point(point)

            if CliManager.VERBOSE_RERANK:
                self.format_chunk(point.payload['chunk_text'])

    def format_expanded_deduped_points(self, points: List[ScoredPoint]) -> None:
        """
        Format chunks of expanded and deduplicated points.
        :param points: Expanded and deduplicated points.
        """
        if len(points) == 0:
            self.logger.info(f"⚠️  No expanded and deduplicated results")
            return

        self.logger.info(f"✅  Expanded and deduplicated down to ({len(points)}) chunk(s):")

        for point in points:

            assert point.payload is not None

            self.format_point(point)

            if CliManager.VERBOSE_RERANK:
                self.format_chunk(point.payload['chunk_text'])

    def format_chunk(self, chunk: str) -> None:
        """
        Format chunk.
        :param chunk: Chunk.
        """
        self.console.print(Panel(f"{chunk}", title="Chunk", style="orange3", border_style="orange3"))

    def format_question(self, question: str) -> None:
        """
        Format question.
        :param question: Question.
        """
        self.console.print(Panel(f"{question}", title="Question", style="magenta", border_style="magenta"))

    def format_query(self, query_result: QuerySchema, answer_text: str):
        """
        Format query.
        :param query_result: Query result.
        :param answer_text: Formatted answer.
        """
        if query_result.is_rejected:
            self.console.print(
                Panel(f"{query_result.rejection_reason}", title="Query rejected", style="red", border_style="red")
            )
        else:
            self.console.print(Panel(f"{answer_text}", title="Answer", style="green", border_style="green"))
