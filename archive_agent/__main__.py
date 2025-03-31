# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from typing import List

from archive_agent.config.ConfigManager import ConfigManager
from archive_agent.watchlist.WatchlistManager import WatchlistManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Archive Agent: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Archive Agent track your files, syncs changes, and powers smart queries.",
)


config = ConfigManager()
watchlist = WatchlistManager()


@app.command()
def watch(pattern: str, additional_patterns: List[str] = typer.Argument(None)) -> None:
    """
    Specify one or more patterns to be watched.
    """
    patterns = [pattern] + (additional_patterns or [])
    raise NotImplementedError


@app.command()
def unwatch(pattern: str, additional_patterns: List[str] = typer.Argument(None)) -> None:
    """
    Specify one or more patterns to be unwatched.
    """
    patterns = [pattern] + (additional_patterns or [])
    raise NotImplementedError


# noinspection PyShadowingBuiltins
@app.command()
def list() -> None:
    """
    Displays watched and unwatched patterns.
    """
    raise NotImplementedError


@app.command()
def commit() -> None:
    """
    Resolves patterns, detects changes, and syncs Qdrant database.
    """
    raise NotImplementedError


@app.command()
def search(question: str) -> None:
    """
    Lists paths matching the question.
    """
    raise NotImplementedError


@app.command()
def query(question: str) -> None:
    """
    Answers your question using RAG.
    """
    raise NotImplementedError


if __name__ == "__main__":
    app()
