#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
import logging
from typing import Callable, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from qdrant_client.models import ScoredPoint

from archive_agent.ai.AiResult import AiResult

from archive_agent.ai_schema.QuerySchema import QuerySchema

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

    @staticmethod
    def prompt(message: str, is_cmd: bool, **kwargs) -> str:
        """
        Prompt user with message.
        :param message: Message.
        :param is_cmd: Enables "> " command style prompt.
        :param kwargs: Additional arguments for typer.prompt.
        :return: User input.
        """
        if is_cmd:
            logger.info(f"🧠 Archive Agent: {message}")
            return typer.prompt("", prompt_suffix="> ", **kwargs)
        else:
            logger.info(f"🧠 Archive Agent")
            return typer.prompt(message, prompt_suffix="", **kwargs)

    def format_openai_chunk(
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
        logger.info(f"Chunking...")

        if CliManager.VERBOSE_CHUNK:
            self.console.print(Panel(f"{line_numbered_text}", title="Text", style="blue", border_style="blue"))

        logger.info("🧠 I'm chunking …")

        result = callback()

        if CliManager.VERBOSE_USAGE:
            logger.info(f"Used ({result.total_tokens}) AI API token(s) for chunking")

        if CliManager.VERBOSE_CHUNK:
            self.format_json(result.output_text)

        return result

    def format_openai_embed(
            self,
            callback: Callable[[], AiResult],
            chunk: str,
    ) -> AiResult:
        """
        Format chunk to be embedded.
        :param callback: Embed callback returning AI result.
        :param chunk: Chunk.
        :return: AI result.
        """
        logger.info(f"Embedding...")

        if CliManager.VERBOSE_EMBED:
            self.format_chunk(chunk)

        logger.info("🧠 I'm embedding …")

        result = callback()

        if CliManager.VERBOSE_USAGE:
            logger.info(f"Used ({result.total_tokens}) AI API token(s) for embedding")

        return result

    def format_openai_query(
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
        logger.info(f"Querying...")

        if CliManager.VERBOSE_QUERY:
            self.console.print(Panel(f"{prompt}", title="Query", style="magenta", border_style="magenta"))

        logger.info("🧠 I'm thinking …")

        result = callback()

        if CliManager.VERBOSE_USAGE:
            logger.info(f"Used ({result.total_tokens}) AI API token(s) for query")

        if CliManager.VERBOSE_QUERY:
            self.format_json(result.output_text)

        return result

    def format_openai_vision(
            self,
            callback: Callable[[], AiResult],
    ) -> AiResult:
        """
        Format AI result of vision callback.
        :param callback: Vision callback returning AI result.
        :return: AI result.
        """
        logger.info("🧠 I'm looking at it …")

        result = callback()

        if CliManager.VERBOSE_VISION:
            self.format_json(result.output_text)

        if CliManager.VERBOSE_USAGE:
            logger.info(f"Used ({result.total_tokens}) AI API token(s) for vision")

        return result

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

        if len(points) > 0:
            logger.info(f"🧠 I found something: ({len(points)}) matching chunk(s)")
        else:
            logger.info(f"🧠 I found nothing")

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

    def format_answer(self, query_result: QuerySchema) -> str:
        """
        Format answer.
        :param query_result: Query result.
        :return: Formatted answer, or empty string if rejected.
        """
        if query_result.reject:
            self.console.print(
                Panel(f"{query_result.rejection_reason}", title="Query rejected", style="red", border_style="red")
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

        self.console.print(Panel(f"{answer_text}", title="Answer", style="green", border_style="green"))

        logger.info("🧠 That's it!")

        return answer_text
