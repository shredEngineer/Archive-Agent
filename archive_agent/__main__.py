#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from pathlib import Path
from typing import List

from archive_agent.util import CliManager
from archive_agent.config import ConfigManager
from archive_agent.watchlist import WatchlistManager
from archive_agent.openai_ import OpenAiManager
from archive_agent.data import ChunkManager
from archive_agent.qdrant_ import QdrantManager
from archive_agent.core import CommitManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Archive Agent: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


settings_path = Path.home() / ".archive-agent-settings"
profile_path = settings_path / "default"

cli = CliManager()
config = ConfigManager(profile_path)
watchlist = WatchlistManager(profile_path)
openai = OpenAiManager(
    cli=cli,
    model_embed=config.data[config.OPENAI_MODEL_EMBED],
    model_query=config.data[config.OPENAI_MODEL_QUERY],
    model_vision=config.data[config.OPENAI_MODEL_VISION],
)
chunker = ChunkManager(
    openai=openai,
    sentences_max=config.data[config.CHUNK_SENTENCES_MAX],
)
qdrant = QdrantManager(
    cli=cli,
    openai=openai,
    chunker=chunker,
    server_url=config.data[config.QDRANT_SERVER_URL],
    collection=config.data[config.QDRANT_COLLECTION],
    vector_size=config.data[config.QDRANT_VECTOR_SIZE],
    score_min=config.data[config.QDRANT_SCORE_MIN],
    chunks_max=config.data[config.QDRANT_CHUNKS_MAX],
)
committer = CommitManager(watchlist, qdrant)


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
        patterns = [typer.prompt("Include pattern")]

    for pattern in patterns:
        watchlist.include(pattern)


# noinspection PyShadowingNames
@app.command()
def exclude(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Add excluded pattern(s).
    """
    if not patterns:
        patterns = [typer.prompt("Exclude pattern")]

    for pattern in patterns:
        watchlist.exclude(pattern)


# noinspection PyShadowingNames
@app.command()
def remove(patterns: List[str] = typer.Argument(None)) -> None:
    """
    Remove previously included / excluded pattern(s).
    """
    if not patterns:
        patterns = [typer.prompt("Remove pattern")]

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
    committer.commit()

    openai.usage()


@app.command()
def search(question: str = typer.Argument(None)) -> None:
    """
    List files matching the question.
    """
    if question is None:
        question = typer.prompt("Type your question")

    _chunks = qdrant.search(question)


@app.command()
def query(question: str = typer.Argument(None)) -> None:
    """
    Get answer to question using RAG.
    """
    if question is None:
        question = typer.prompt("Type your question")

    _answer = qdrant.query(question)


if __name__ == "__main__":
    app()
