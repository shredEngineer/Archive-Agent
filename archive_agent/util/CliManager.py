#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from rich import print
from rich.panel import Panel
import logging
from typing import Callable, List, Any

from qdrant_client.models import ScoredPoint

logger = logging.getLogger(__name__)


class CliManager:
    """
    CLI manager.
    """

    def __init__(self):
        """
        Initialize CLI manager.
        """
        pass

    @staticmethod
    def format_openai_embed(callback: Callable[[], Any], chunk: str) -> Any:
        """
        Format OpenAI response of embed callback.
        :param callback: Embed callback returning OpenAI response.
        :param chunk: Chunk.
        :return: OpenAI response.
        """
        logger.info(f" - Embedding...")
        print(Panel(f"[white]{chunk}"))
        response = callback()
        logger.info(f" - Used ({response.usage.total_tokens}) token(s)")
        return response

    @staticmethod
    def format_openai_query(callback: Callable[[], Any], prompt: str) -> Any:
        """
        Format OpenAI response of query callback.
        :param callback: Query callback returning OpenAI response.
        :param prompt: Prompt.
        :return: OpenAI response.
        """
        logger.info(f" - Querying...")
        print(Panel(f"[red]{prompt}"))
        response = callback()
        print(Panel(f"[green]{response.output_text}"))
        logger.info(f" - Used ({response.usage.total_tokens}) token(s)")
        return response

    @staticmethod
    def format_openai_vision(callback: Callable[[], Any]) -> Any:
        """
        Format OpenAI response of vision callback.
        :param callback: Vision callback returning OpenAI response.
        :return: OpenAI response.
        """
        logger.info(f" - Image vision...")
        response = callback()
        print(Panel(f"[green]{response.output_text}"))
        logger.info(f" - Used ({response.usage.total_tokens}) token(s)")
        return response

    @staticmethod
    def format_points(points: List[ScoredPoint]) -> None:
        """
        Format chunks of retreived points.
        :param points: Retrieved points.
        """
        for point in points:
            score_percent = point.score * 100
            logger.info(f" - ({score_percent:.2f} %) matching chunk in file: '{point.payload['file_path']}':")
            print(Panel(f"[yellow]{point.payload['chunk']}"))

        logger.warning(f" - Found ({len(points)}) matching chunks")
