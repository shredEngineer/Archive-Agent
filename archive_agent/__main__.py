#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import pathlib
import subprocess
from typing import List

from archive_agent.core import ContextManager

logger = logging.getLogger(__name__)


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
    context = ContextManager()

    if not patterns:
        patterns = [typer.prompt("Include pattern")]

    for pattern in patterns:
        context.watchlist.include(pattern)


# noinspection PyShadowingNames
@app.command()
def exclude(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add excluded pattern(s).
    """
    context = ContextManager()

    if not patterns:
        patterns = [typer.prompt("Exclude pattern")]

    for pattern in patterns:
        context.watchlist.exclude(pattern)


# noinspection PyShadowingNames
@app.command()
def remove(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Remove previously included / excluded pattern(s).
    """
    context = ContextManager()

    if not patterns:
        patterns = [typer.prompt("Remove pattern")]

    for pattern in patterns:
        context.watchlist.remove(pattern)


@app.command()
def patterns() -> None:
    """
    Show the list of included / excluded patterns.
    """
    context = ContextManager()

    context.watchlist.patterns()


@app.command()
def track() -> None:
    """
    Resolve all patterns and track changed files.
    """
    context = ContextManager()

    context.watchlist.track()


# noinspection PyShadowingBuiltins
@app.command()
def list() -> None:
    """
    Show the full list of tracked files.
    """
    context = ContextManager()

    context.watchlist.list()


@app.command()
def diff() -> None:
    """
    Show the list of changed files.
    """
    context = ContextManager()

    context.watchlist.diff()


@app.command()
def commit() -> None:
    """
    Sync changed files with the Qdrant database.
    """
    context = ContextManager()

    context.committer.commit()

    context.openai.usage()


@app.command()
def search(question: str = typer.Argument(None)) -> None:
    """
    List files matching the question.
    """
    context = ContextManager()

    if question is None:
        question = typer.prompt("Type your question")

    _chunks = context.qdrant.search(question)

    context.openai.usage()


@app.command()
def query(question: str = typer.Argument(None)) -> None:
    """
    Get answer to question using RAG.
    """
    context = ContextManager()

    if question is None:
        question = typer.prompt("Type your question")

    _query_result = context.qdrant.query(question)

    context.openai.usage()


@app.command()
def gui() -> None:
    """
    Launch browser-based GUI.
    """
    gui_path = pathlib.Path(__file__).parent / "core" / "GuiManager.py"
    subprocess.run(["streamlit", "run", str(gui_path)])


if __name__ == "__main__":
    app()
