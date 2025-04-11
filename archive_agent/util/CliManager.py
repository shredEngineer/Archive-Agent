#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
import logging
from typing import Callable, List, Any

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

# TODO: Use specific type; pyright doesn't like:
#       from openai.types.responses.response import Response
Response = Any

from qdrant_client.models import ScoredPoint

from archive_agent.schema import QuerySchema
from archive_agent.util.format import format_file, format_time

logger = logging.getLogger(__name__)


class CliManager:
    """
    CLI manager.
    """

    VERBOSE_CHUNK: bool = True
    VERBOSE_EMBED: bool = True
    VERBOSE_QUERY: bool = True
    VERBOSE_VISION: bool = True
    VERBOSE_RETRIEVAL: bool = True
    VERBOSE_USAGE: bool = True

    def __init__(self):
        """
        Initialize CLI manager.
        """
        # Console with markup disabled to avoid Rich parsing crashes.
        self.console = Console(markup=False)

    def format_json(self, text: str) -> None:
        """
        Format text as JSON.
        :param text: Text.
        """
        try:
            data = json.loads(text)
            pretty = Pretty(data, expand_all=True)
            self.console.print(Panel(pretty, title="Structured output", border_style="white"))
        except json.JSONDecodeError:
            self.console.print(Panel(f"[white]{text}", title="Raw output", border_style="red"))

    def format_openai_chunk(self, callback: Callable[[], Response], line_numbered_text: str) -> Response:
        """
        Format OpenAI response of chunk callback.
        :param callback: Chunk callback returning OpenAI response.
        :param line_numbered_text: Text with line numbers.
        :return: OpenAI response.
        """
        logger.info(f"Chunking...")

        if CliManager.VERBOSE_CHUNK:
            self.console.print(Panel(f"[blue]{line_numbered_text}", title="Text", border_style="white"))

        response = callback()

        if CliManager.VERBOSE_CHUNK:
            self.format_json(response.output_text)

        if CliManager.VERBOSE_USAGE and response.usage is not None:
            logger.info(f"Used ({response.usage.total_tokens}) OpenAI API token(s) for chunking")

        return response

    def format_openai_embed(self, callback: Callable[[], Response], chunk: str) -> Response:
        """
        Format OpenAI response of embed callback.
        :param callback: Embed callback returning OpenAI response.
        :param chunk: Chunk.
        :return: OpenAI response.
        """
        logger.info(f"Embedding...")

        if CliManager.VERBOSE_EMBED:
            self.format_chunk(chunk)

        response = callback()

        if CliManager.VERBOSE_USAGE and response.usage is not None:
            logger.info(f"Used ({response.usage.total_tokens}) OpenAI API token(s) for embedding")

        return response

    def format_openai_query(self, callback: Callable[[], Response], prompt: str) -> Response:
        """
        Format OpenAI response of query callback.
        :param callback: Query callback returning OpenAI response.
        :param prompt: Prompt.
        :return: OpenAI response.
        """
        logger.info(f"Querying...")

        if CliManager.VERBOSE_QUERY:
            self.console.print(Panel(f"[red]{prompt}", title="Query", border_style="white"))

        response = callback()

        if CliManager.VERBOSE_QUERY:
            self.format_json(response.output_text)

        if CliManager.VERBOSE_USAGE and response.usage is not None:
            logger.info(f"Used ({response.usage.total_tokens}) OpenAI API token(s) for query")

        return response

    def format_openai_vision(self, callback: Callable[[], Response]) -> Response:
        """
        Format OpenAI response of vision callback.
        :param callback: Vision callback returning OpenAI response.
        :return: OpenAI response.
        """
        logger.info(f"Image vision...")

        response = callback()

        if CliManager.VERBOSE_VISION:
            self.format_json(response.output_text)

        if CliManager.VERBOSE_USAGE and response.usage is not None:
            logger.info(f"Used ({response.usage.total_tokens}) OpenAI API token(s) for vision")

        return response

    def format_points(self, points: List[ScoredPoint]) -> None:
        """
        Format chunks of retreived points.
        :param points: Retrieved points.
        """
        for point in points:

            assert point.payload is not None

            logger.info(
                f"({point.score * 100:.2f} %) matching "
                f"chunk ({point.payload['chunk_index'] + 1}) / ({point.payload['chunks_total']}) "
                f"of {format_file(point.payload['file_path'])} "
                f"@ {format_time(point.payload['file_mtime'])}:"
            )

            if CliManager.VERBOSE_RETRIEVAL:
                self.format_chunk(point.payload['chunk_text'])

        logger.warning(f"Found ({len(points)}) matching chunk(s)")

    def format_chunk(self, chunk: str) -> None:
        """
        Format chunk.
        :param chunk: Chunk.
        """
        self.console.print(Panel(f"[yellow]{chunk}", title="Chunk", border_style="white"))

    def format_question(self, question: str) -> None:
        """
        Format question.
        :param question: Question.
        """
        self.console.print(Panel(f"[white]{question}", title="Question", border_style="red"))

    def format_answer(self, query_result: QuerySchema) -> str:
        """
        Format answer.
        :param query_result: Query result.
        :return: Formatted answer, or empty string if rejected.
        """
        if query_result.reject:
            self.console.print(
                Panel(f"[white]{query_result.rejection_reason}", title="Query rejected", border_style="red")
            )
            return ""

        answer_list_text = "\n".join([
            f"- {answer_text}"
            for answer_text in query_result.answer_list
        ])

        chunk_ref_list_text = "\n".join([
            f"- {chunk_ref}"
            for chunk_ref in query_result.chunk_ref_list
        ])

        follow_up_list_text = "\n".join([
            f"- {follow_up}"
            for follow_up in query_result.follow_up_list
        ])

        answer_text = "\n\n".join([
            f"### Question",
            f"**{query_result.question_rephrased}**",
            f"### Answers",
            f"{answer_list_text}",
            f"### Conclusion",
            f"**{query_result.answer_conclusion}**",
            f"### References",
            f"{chunk_ref_list_text}",
            f"### Follow-Up Questions",
            f"{follow_up_list_text}",
        ])

        self.console.print(Panel(f"[white]{answer_text}", title="Answer", border_style="green"))

        return answer_text
