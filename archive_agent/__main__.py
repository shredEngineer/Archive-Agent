#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from pathlib import Path
from typing import List

from archive_agent.config.ConfigManager import ConfigManager
from archive_agent.watchlist.WatchlistManager import WatchlistManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Archive Agent: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


settings_path = Path.home() / ".archive-agent-settings"
profile_path = settings_path / "default"

config = ConfigManager(profile_path)
watchlist = WatchlistManager(profile_path)


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Archive Agent tracks your files, syncs changes, and powers smart queries.",
)


# noinspection PyShadowingNames
@app.command()
def include(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add included pattern(s).
    """
    if not patterns:
        print()
        pattern = typer.prompt("Include pattern")
        patterns = [pattern]

    for pattern in patterns:
        watchlist.include(pattern)


# noinspection PyShadowingNames
@app.command()
def exclude(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add excluded pattern(s).
    """
    if not patterns:
        print()
        pattern = typer.prompt("Exclude pattern")
        patterns = [pattern]

    for pattern in patterns:
        watchlist.exclude(pattern)


# noinspection PyShadowingNames
@app.command()
def remove(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Remove previously included / excluded pattern(s).
    """
    if not patterns:
        print()
        pattern = typer.prompt("Remove pattern")
        patterns = [pattern]

    for pattern in patterns:
        watchlist.remove(pattern)


@app.command()
def patterns() -> None:
    """
    Show the list of included / excluded patterns.
    """
    watchlist.patterns()


@app.command()
def track() -> None:
    """
    Resolve all patterns and track changed files.
    """
    watchlist.track()


# noinspection PyShadowingBuiltins
@app.command()
def list() -> None:
    """
    Show the full list of tracked files.
    """
    watchlist.list()


@app.command()
def diff() -> None:
    """
    Show the list of changed files.
    """
    watchlist.diff()


@app.command()
def commit() -> None:
    """
    Sync changed files with the Qdrant database.
    """
    raise NotImplementedError


@app.command()
def search(question: str = typer.Argument(None)) -> None:
    """
    List files matching the question.
    """
    if question:
        pass
    else:
        print()
        question = typer.prompt("Type your question")
    raise NotImplementedError


@app.command()
def query(question: str = typer.Argument(None)) -> None:
    """
    Get answer to question using RAG.
    """
    if question:
        pass
    else:
        print()
        question = typer.prompt("Type your question")
    raise NotImplementedError


if __name__ == "__main__":
    app()
