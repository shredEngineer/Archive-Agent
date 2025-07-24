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
    help="Find your files with natural language and ask questions.",
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

    if _context.watchlist.isEmpty():
        logger.info("💡  Include your first files  ('archive-agent include')")

    raise typer.Exit()


# noinspection PyShadowingNames
@app.command()
def switch(profile_name: str = typer.Argument("")) -> None:
    """
    Create or switch profile.
    """
    logger.info("💡  You can enter an existing or NEW name")

    _context = ContextManager(profile_name=profile_name)


@app.command()
def config() -> None:
    """
    Open current profile config in nano.
    """
    context = ContextManager()
    subprocess.run(["nano", str(context.config.file_path)])


# noinspection PyShadowingNames
@app.command()
def include(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add included pattern(s).
    """
    context = ContextManager()

    if not patterns:
        patterns = [context.cli.prompt("🤔  Include pattern?", is_cmd=True).strip()]

    for pattern in patterns:
        context.watchlist.include(pattern)

    logger.info("💡  Don't forget to track files  ('archive-agent track')")


# noinspection PyShadowingNames
@app.command()
def exclude(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add excluded pattern(s).
    """
    context = ContextManager()

    if not patterns:
        patterns = [context.cli.prompt("🤔  Exclude pattern?", is_cmd=True).strip()]

    for pattern in patterns:
        context.watchlist.exclude(pattern)

    logger.info("💡  Don't forget to track files  ('archive-agent track')")


# noinspection PyShadowingNames
@app.command()
def remove(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Remove previously included / excluded pattern(s).
    """
    context = ContextManager()

    if not patterns:
        patterns = [context.cli.prompt("🤔  Remove pattern?", is_cmd=True).strip()]

    for pattern in patterns:
        context.watchlist.remove(pattern)

    logger.info("💡  Don't forget to track files  ('archive-agent track')")


@app.command()
def patterns() -> None:
    """
    Show the list of included / excluded patterns.
    """
    context = ContextManager()

    context.watchlist.patterns()

    if context.watchlist.isEmpty():
        logger.info("💡  Include your first files  ('archive-agent include')")


@app.command()
def track() -> None:
    """
    Resolve all patterns and track changed files.
    """
    context = ContextManager()

    n = context.watchlist.track()

    if n > 0:
        logger.info("💡  Commit your tracked files now  ('archive-agent commit')")
        logger.info("💡  OR list added/removed/changed  ('archive-agent diff')")

    if context.watchlist.isEmpty():
        logger.info("💡  Include your first files  ('archive-agent include')")
    else:
        logger.info("💡  Ready to get some answers?  ('archive-agent query')")


# noinspection PyShadowingBuiltins
@app.command()
def list() -> None:
    """
    Show the list of tracked files.
    """
    context = ContextManager()

    logger.info("💡  Always track your files first  ('archive-agent track')")

    context.watchlist.list()


@app.command()
def diff() -> None:
    """
    Show the list of changed files.
    """
    context = ContextManager()

    logger.info("💡  Always track your files first  ('archive-agent track')")

    context.watchlist.diff()


@app.command()
def commit(
        nocache: bool = typer.Option(
            False,
            "--nocache",
            help="Invalidate the AI cache for this commit."
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="Show additional chunking and embedding information."
        ),
) -> None:
    """
    Sync changed files with the Qdrant database.
    """
    context = ContextManager(invalidate_cache=nocache, verbose=verbose)

    logger.info("💡  Always track your files first  ('archive-agent track')")

    context.committer.commit()

    context.ai_base.usage()

    if context.watchlist.isEmpty():
        logger.info("💡  Include your first files  ('archive-agent include')")
    else:
        logger.info("💡  Ready to get some answers?  ('archive-agent query')")


@app.command()
def update(
        nocache: bool = typer.Option(
            False,
            "--nocache",
            help="Invalidate the AI cache for this commit."
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="Show additional chunking and embedding information."
        ),
) -> None:
    """
    `track` and then `commit` in one go.
    """
    context = ContextManager(invalidate_cache=nocache, verbose=verbose)

    context.watchlist.track()

    context.committer.commit()

    context.ai_base.usage()

    if context.watchlist.isEmpty():
        logger.info("💡  Include your first files  ('archive-agent include')")
    else:
        logger.info("💡  Ready to get some answers?  ('archive-agent query')")


@app.command()
def search(
        question: str = typer.Argument(None),
        nocache: bool = typer.Option(
            False,
            "--nocache",
            help="Invalidate the AI cache for this search."
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="Show additional embedding and reranking information."
        ),
) -> None:
    """
    List files relevant to the question.
    """
    context = ContextManager(invalidate_cache=nocache, verbose=verbose)

    logger.info("💡  Ask your question — be as specific as possible")

    if question is None:
        question = context.cli.prompt("😎  Ask something…", is_cmd=True)

    _points = context.qdrant.search(question)

    context.ai_base.usage()


@app.command()
def query(
        question: str = typer.Argument(None),
        nocache: bool = typer.Option(
            False,
            "--nocache",
            help="Invalidate the AI cache for this query."
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="Show additional embedding and reranking information."
        ),
) -> None:
    """
    Get answer to question using RAG.
    """
    context = ContextManager(invalidate_cache=nocache, verbose=verbose)

    logger.info("💡  Ask your question — be as specific as possible")

    if question is None:
        question = context.cli.prompt("😎  Ask something…", is_cmd=True)

    _query_result, _answer_text = context.qdrant.query(question)

    context.ai_base.usage()

    logger.info("⚡  Process finished")


@app.command()
def gui() -> None:
    """
    Launch browser-based GUI.
    """
    logger.info("💡  GUI is starting, just a sec…")

    gui_path = pathlib.Path(__file__).parent / "core" / "GuiManager.py"
    subprocess.run(["streamlit", "run", str(gui_path)])


@app.command()
def mcp() -> None:
    """
    Start MCP server.
    """
    context = ContextManager()

    logger.info("💡  GUI is starting, just a sec…")

    # TODO: Allow for graceful CTRL+C shutdown without the `asyncio.exceptions.CancelledError`
    mcp_server = McpServer(context=context, port=context.config.data[context.config.MCP_SERVER_PORT])
    mcp_server.start()

    context.ai_base.usage()


if __name__ == "__main__":
    app()
