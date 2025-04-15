#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging

from archive_agent.ai.AiManager import AiManager

from archive_agent.data.FileData import FileData

from archive_agent.db.QdrantManager import QdrantManager

from archive_agent.watchlist.WatchlistManager import WatchlistManager

from archive_agent.util.format import format_file

logger = logging.getLogger(__name__)


class CommitManager:
    """
    Commit manager.
    """

    def __init__(self, watchlist: WatchlistManager, ai: AiManager, qdrant: QdrantManager):
        """
        Initialize commit manager.
        :param watchlist: Watchlist manager.
        :param ai: AI manager.
        :param qdrant: Qdrant manager.
        """
        self.watchlist = watchlist
        self.ai = ai
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

        tracked_file_data = [
            FileData(ai=self.ai, file_path=file_path, file_meta=file_meta)
            for file_path, file_meta in tracked.items()
        ]

        tracked_unprocessable = [file_data for file_data in tracked_file_data if not file_data.is_processable()]
        tracked_processable = [file_data for file_data in tracked_file_data if file_data.is_processable()]

        if len(tracked) == 0:
            logger.info(f"No {cli_hint} files to commit")

        else:
            logger.info(f"Committing ({len(tracked)}) {cli_hint} file(s)...")

            for file_data in tracked_unprocessable:
                logger.warning(f"IGNORING unprocessable {format_file(file_data.file_path)}")
                if file_data.file_meta['diff'] == self.watchlist.DIFF_REMOVED:
                    _success = self.qdrant.remove(file_data)
                    self.watchlist.diff_mark_resolved(file_data)

            for file_data in tracked_processable:
                match diff_option:
                    case self.watchlist.DIFF_ADDED:
                        if self.qdrant.add(file_data):
                            self.watchlist.diff_mark_resolved(file_data)

                    case self.watchlist.DIFF_CHANGED:
                        if self.qdrant.change(file_data):
                            self.watchlist.diff_mark_resolved(file_data)

                    case self.watchlist.DIFF_REMOVED:
                        if self.qdrant.remove(file_data):
                            self.watchlist.diff_mark_resolved(file_data)

                    case _:
                        logger.error(f"Invalid diff option: '{diff_option}'")
                        raise typer.Exit(code=1)
