#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from typing import List

from archive_agent.core import ContextManager

logger = logging.getLogger(__name__)


context = ContextManager()


# noinspection PyShadowingNames
@context.app.command()
def include(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add included pattern(s).
    """
    if not patterns:
        patterns = [typer.prompt("Include pattern")]

    for pattern in patterns:
        context.watchlist.include(pattern)


# noinspection PyShadowingNames
@context.app.command()
def exclude(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add excluded pattern(s).
    """
    if not patterns:
        patterns = [typer.prompt("Exclude pattern")]

    for pattern in patterns:
        context.watchlist.exclude(pattern)


# noinspection PyShadowingNames
@context.app.command()
def remove(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Remove previously included / excluded pattern(s).
    """
    if not patterns:
        patterns = [typer.prompt("Remove pattern")]

    for pattern in patterns:
        context.watchlist.remove(pattern)


@context.app.command()
def patterns() -> None:
    """
    Show the list of included / excluded patterns.
    """
    context.watchlist.patterns()


@context.app.command()
def track() -> None:
    """
    Resolve all patterns and track changed files.
    """
    context.watchlist.track()


# noinspection PyShadowingBuiltins
@context.app.command()
def list() -> None:
    """
    Show the full list of tracked files.
    """
    context.watchlist.list()


@context.app.command()
def diff() -> None:
    """
    Show the list of changed files.
    """
    context.watchlist.diff()


@context.app.command()
def commit() -> None:
    """
    Sync changed files with the Qdrant database.
    """
    context.committer.commit()

    context.openai.usage()


@context.app.command()
def search(question: str = typer.Argument(None)) -> None:
    """
    List files matching the question.
    """
    if question is None:
        question = typer.prompt("Type your question")

    _chunks = context.qdrant.search(question)

    context.openai.usage()


@context.app.command()
def query(question: str = typer.Argument(None)) -> None:
    """
    Get answer to question using RAG.
    """
    if question is None:
        question = typer.prompt("Type your question")

    _answer = context.qdrant.query(question)

    context.openai.usage()


@context.app.command()
def gui() -> None:
    """
    Launch browser-based GUI.
    """
    import subprocess
    import pathlib
    gui_path = pathlib.Path(__file__).parent / "core" / "GuiManager.py"
    subprocess.run(["streamlit", "run", str(gui_path)])


if __name__ == "__main__":
    context.app()
