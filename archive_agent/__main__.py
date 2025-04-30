#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import pathlib
import subprocess
from typing import List

logger = logging.getLogger(__name__)

logger.info("Starting...")

from archive_agent.core.ContextManager import ContextManager

from archive_agent.mcp_server.McpServer import McpServer


app = typer.Typer(
    invoke_without_command=True,
    add_completion=False,
    help="Archive Agent tracks your files, syncs changes, and powers smart queries.",
)


@app.callback()
def root(ctx: typer.Context) -> None:
    """
    Root callback that runs when no subcommand is provided.
    """
    if ctx.invoked_subcommand is not None:
        return  # Handle subcommand.

    _context = ContextManager()

    # Show help.
    typer.echo(ctx.get_help())
    raise typer.Exit()


# noinspection PyShadowingNames
@app.command()
def switch(profile_name: str = typer.Argument("")) -> None:
    """
    Create or switch profile.
    """
    _context = ContextManager(profile_name=profile_name)


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
    Show the list of tracked files.
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

    context.ai.usage()


@app.command()
def update() -> None:
    """
    `track` and then `commit` in one go.
    """
    context = ContextManager()

    context.watchlist.track()

    context.committer.commit()

    context.ai.usage()


@app.command()
def search(question: str = typer.Argument(None)) -> None:
    """
    List files relevant to the question.
    """
    context = ContextManager()

    if question is None:
        question = typer.prompt("Type your question")

    _chunks = context.qdrant.search(question)

    context.ai.usage()


@app.command()
def query(question: str = typer.Argument(None)) -> None:
    """
    Get answer to question using RAG.
    """
    context = ContextManager()

    if question is None:
        question = typer.prompt("Type your question")

    _query_result, _answer_text = context.qdrant.query(question)

    context.ai.usage()


@app.command()
def gui() -> None:
    """
    Launch browser-based GUI.
    """
    gui_path = pathlib.Path(__file__).parent / "core" / "GuiManager.py"
    subprocess.run(["streamlit", "run", str(gui_path)])


@app.command()
def mcp() -> None:
    """
    Start MCP server.
    """
    context = ContextManager()

    # TODO: Allow for graceful CTRL+C shutdown without the `asyncio.exceptions.CancelledError`
    mcp_server = McpServer(context=context, port=context.config.data[context.config.MCP_SERVER_PORT])
    mcp_server.start()

    context.ai.usage()


if __name__ == "__main__":
    app()
