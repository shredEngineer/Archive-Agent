#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging

from archive_agent.data.FileData import FileData

from archive_agent.db.QdrantManager import QdrantManager

from archive_agent.watchlist.WatchlistManager import WatchlistManager

from archive_agent.util.format import format_file

logger = logging.getLogger(__name__)


class CommitManager:
    """
    Commit manager.
    """

    def __init__(self, watchlist: WatchlistManager, qdrant: QdrantManager):
        """
        Initialize commit manager.
        :param watchlist: Watchlist manager.
        :param qdrant: Qdrant manager.
        """
        self.watchlist = watchlist
        self.qdrant = qdrant

    def commit(self) -> None:
        """
        Commit all tracked files.
        """
        self.commit_diff(self.watchlist.DIFF_ADDED, "added")
        self.commit_diff(self.watchlist.DIFF_CHANGED, "changed")
        self.commit_diff(self.watchlist.DIFF_REMOVED, "removed")

    def commit_diff(self, diff_option: str, cli_hint: str) -> None:
        """
        Commit tracked files filtered for diff option.
        :param diff_option: Diff option.
        :param cli_hint: CLI hint.
        """
        tracked = self.watchlist.diff_filter(diff_option)

        tracked_unprocessable = {f: m for f, m in tracked.items() if not FileData.is_processable(f)}
        tracked_processable = {f: m for f, m in tracked.items() if FileData.is_processable(f)}

        if len(tracked) == 0:
            logger.info(f"No {cli_hint} files to commit")

        else:
            logger.info(f"Committing ({len(tracked)}) {cli_hint} file(s)...")

            for file_path, meta in tracked_unprocessable.items():
                logger.warning(f"Unprocessable {format_file(file_path)}")
                if meta['diff'] == self.watchlist.DIFF_REMOVED:
                    _success = self.qdrant.remove(file_path)
                    self.watchlist.diff_mark_resolved(file_path)

            for file_path, meta in tracked_processable.items():
                match diff_option:
                    case self.watchlist.DIFF_ADDED:
                        if self.qdrant.add(file_path, meta['mtime']):
                            self.watchlist.diff_mark_resolved(file_path)

                    case self.watchlist.DIFF_CHANGED:
                        if self.qdrant.change(file_path, meta['mtime']):
                            self.watchlist.diff_mark_resolved(file_path)

                    case self.watchlist.DIFF_REMOVED:
                        if self.qdrant.remove(file_path):
                            self.watchlist.diff_mark_resolved(file_path)

                    case _:
                        logger.error(f"Invalid diff option: '{diff_option}'")
                        raise typer.Exit(code=1)
