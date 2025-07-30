#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
import logging
import queue
import threading
from contextlib import contextmanager
from logging import Handler, LogRecord
from typing import Callable, List, Dict, cast, Optional, Any

import typer
from rich.console import Console, RenderableType, Group
from rich.live import Live
from rich.logging import RichHandler
from rich.panel import Panel
from rich.pretty import Pretty
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from qdrant_client.models import ScoredPoint

from archive_agent.ai.AiResult import AiResult

from archive_agent.ai.query.AiQuery import QuerySchema
from archive_agent.ai.vision.AiVisionSchema import VisionSchema

from archive_agent.util.format import format_chunk_brief, get_point_reference_info


class QueueHandler(Handler):
    """
    A logging handler that puts records into a queue.
    """

    def __init__(self, record_queue: queue.Queue):
        """
        Initialize the handler.
        :param record_queue: The queue to put records into.
        """
        super().__init__()
        self.record_queue = record_queue

    def emit(self, record: LogRecord):
        """
        Emit a record.
        """
        self.record_queue.put(record)


def _printer_thread_target(
        live: Live,
        q: queue.Queue,
        rich_handler: RichHandler,
        get_renderable: Callable[[], RenderableType]
):
    """
    The target function for the printer thread.
    Pulls items from a queue and prints them to the live console.
    Also, periodically refreshes the live display.
    """
    while True:
        try:
            item = q.get(timeout=0.1)  # Timeout to allow for periodic refresh
            if item is None:  # Sentinel value to signal thread to exit
                break

            if isinstance(item, LogRecord):
                rich_handler.handle(item)
            else:
                live.console.print(item)
            q.task_done()
        except queue.Empty:
            pass  # Timeout occurred, just refresh the display

        live.update(get_renderable())


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
    VERBOSE_USAGE: bool = False  # enabled by --verbose flag

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
        CliManager.VERBOSE_USAGE = verbose

        self.logger = logging.getLogger()

        self.console = Console(markup=False)
        self._output_queue: Optional[queue.Queue] = None

        self.ai_usage_stats = {
            "chunk": 0,
            "embed": 0,
            "rerank": 0,
            "query": 0,
            "vision": 0
        }
        self.lock = threading.Lock()

    @contextmanager
    def live_context(self, live: Live, get_renderable: Callable[[], RenderableType]) -> Any:
        """
        A context manager to correctly handle logging and printing during a Live display.
        It finds the existing RichHandler, redirects its output to the live console,
        and funnels all log messages through a queue to a dedicated printer thread.
        """
        q = queue.Queue()
        self._output_queue = q

        # Find the existing RichHandler from the configured logger.
        original_rich_handler = None
        for handler in self.logger.handlers:
            if isinstance(handler, RichHandler):
                original_rich_handler = handler
                break

        if not original_rich_handler:
            raise RuntimeError("RichHandler not found on the logger. Logging is not configured correctly.")

        # Store the original console and temporarily redirect the handler's output to the live console.
        original_console = original_rich_handler.console
        original_rich_handler.console = live.console

        # Start the printer thread, passing it the *original*, now-redirected handler.
        printer_thread = threading.Thread(
            target=_printer_thread_target,
            args=(live, q, original_rich_handler, get_renderable)
        )
        printer_thread.daemon = True
        printer_thread.start()

        # Temporarily replace the main logger's handlers with the QueueHandler to funnel all logs.
        queue_handler = QueueHandler(q)
        original_handlers = self.logger.handlers[:]
        self.logger.handlers = [queue_handler]

        try:
            yield
        finally:
            # Signal the printer thread to exit and wait for it to finish processing the queue.
            q.put(None)
            printer_thread.join()

            # Restore the original logger handlers.
            self.logger.handlers = original_handlers
            self._output_queue = None

            # IMPORTANT: Restore the original console to the handler.
            if original_rich_handler:
                original_rich_handler.console = original_console

    def _print(self, renderable: RenderableType):
        """
        Internal helper to print to the correct destination (queue or default console).
        """
        if self._output_queue:
            self._output_queue.put(renderable)
        else:
            self.console.print(renderable)

    def update_ai_usage(self, stats: Dict[str, int]):
        """
        Thread-safe method to update AI usage statistics.
        :param stats: A dictionary with token counts to add.
        """
        with self.lock:
            for category, value in stats.items():
                if category in self.ai_usage_stats:
                    self.ai_usage_stats[category] += value

    def get_ai_usage_renderable(self) -> Table:
        """
        Create a Rich Table to display AI usage statistics in a transposed layout.
        :return: A Rich Table object.
        """
        table = Table(
            title="AI Usage",
            show_header=False,
            show_edge=False,
            pad_edge=False,
            box=None,
            padding=(0, 2)
        )

        with self.lock:
            categories = [c.capitalize() for c in self.ai_usage_stats.keys()]
            values = [str(v) for v in self.ai_usage_stats.values()]

            # Define columns based on number of categories + 1 for the labels
            table.add_column(style="cyan", no_wrap=True)
            for _ in categories:
                table.add_column(justify="right", style="magenta")

            table.add_row("Category", *categories)
            table.add_row("Tokens", *values)

        return table

    @contextmanager
    def progress_context(self, title: str, total: int) -> Any:
        """
        A context manager for displaying a progress bar with live logging.
        It sets up a Rich Live display with a progress bar and AI usage stats,
        and ensures all logging is correctly routed.
        :param title: The title for the overall progress bar.
        :param total: The total number of items for the progress bar.
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        )
        overall_task_id = progress.add_task(f"[bold blue]{title}", total=total)

        def get_renderable() -> Group:
            return Group(
                progress,
                self.get_ai_usage_renderable()
            )

        with Live(get_renderable(), screen=False, redirect_stderr=False, transient=True) as live:
            with self.live_context(live, get_renderable):
                yield progress, overall_task_id

    def format_json(self, text: str) -> None:
        """
        Format text as JSON.
        :param text: Text.
        """
        try:
            data = json.loads(text)
            pretty = Pretty(data, expand_all=True)
            self._print(Panel(pretty, title="Structured output", style="blue", border_style="blue"))
        except json.JSONDecodeError:
            self._print(Panel(f"{text}", title="Raw output", style="red", border_style="red"))

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
        if CliManager.VERBOSE_CHUNK:
            self._print(Panel(f"{line_numbered_text}", title="Text", style="blue", border_style="blue"))
            self.logger.info("✨ Awaiting AI chunking…")

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
            self._print(Panel(f"{indexed_chunks_str}", title="Indexed Chunks", style="blue", border_style="blue"))
            self.logger.info("✨ Awaiting AI reranking…")

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
            self.logger.info("✨ Awaiting AI embedding…")

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
            self._print(Panel(f"{prompt}", title="Query", style="magenta", border_style="magenta"))
            self.logger.info("✨ Awaiting AI response…")

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
        if CliManager.VERBOSE_VISION:
            self.logger.info("✨ Awaiting AI vision…")

        result: AiResult = callback()

        if CliManager.VERBOSE_VISION:
            vision_result = cast(VisionSchema, result.parsed_schema)
            if vision_result.is_rejected:
                self._print(
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
        self.logger.info(f"({point.score * 100:>6.2f} %) match: {get_point_reference_info(point, verbose=True)}")

    def format_retrieved_points(self, points: List[ScoredPoint]) -> None:
        """
        Format chunks of retrieved points.
        :param points: Retrieved points.
        """
        if len(points) == 0:
            self.logger.info(f"⚠️ No retrieved results")
            return

        self.logger.info(f"✅ Retrieved ({len(points)}) chunk(s):")

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
            self.logger.info(f"⚠️ No reranked results")
            return

        self.logger.info(f"✅ Reranked and limited down to ({len(points)}) chunk(s):")

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
            self.logger.info(f"⚠️ No expanded and deduplicated results")
            return

        self.logger.info(f"✅ Expanded and deduplicated down to ({len(points)}) chunk(s):")

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
        self._print(Panel(f"{chunk}", title="Chunk", style="orange3", border_style="orange3"))

    def format_question(self, question: str) -> None:
        """
        Format question.
        :param question: Question.
        """
        self._print(Panel(f"{question}", title="Question", style="magenta", border_style="magenta"))

    def format_query(self, query_result: QuerySchema, answer_text: str):
        """
        Format query.
        :param query_result: Query result.
        :param answer_text: Formatted answer.
        """
        if query_result.is_rejected:
            self._print(
                Panel(f"{query_result.rejection_reason}", title="Query rejected", style="red", border_style="red")
            )
        else:
            self._print(Panel(f"{answer_text}", title="Answer", style="green", border_style="green"))

    def usage(self):
        """
        Show AI token usage.
        """
        with self.lock:
            if any(self.ai_usage_stats.values()):
                self.logger.info(
                    f"Used AI API token(s): "
                    f"({self.ai_usage_stats['chunk']}) chunking, "
                    f"({self.ai_usage_stats['embed']}) embedding, "
                    f"({self.ai_usage_stats['rerank']}) reranking, "
                    f"({self.ai_usage_stats['query']}) query, "
                    f"({self.ai_usage_stats['vision']}) vision"
                )
            else:
                self.logger.info("No AI API tokens used")

        self.console.print(self.get_ai_usage_renderable())
