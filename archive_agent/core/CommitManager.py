#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging

from archive_agent.ai.AiManager import AiManager

from archive_agent.config.DecoderSettings import DecoderSettings

from archive_agent.data.FileData import FileData

from archive_agent.db.QdrantManager import QdrantManager

from archive_agent.watchlist.WatchlistManager import FilteredFiles, WatchlistManager

from archive_agent.util.format import format_file

logger = logging.getLogger(__name__)


class CommitManager:
    """
    Commit manager.
    """

    def __init__(
            self,
            watchlist: WatchlistManager,
            ai: AiManager,
            decoder_settings: DecoderSettings,
            qdrant: QdrantManager,
    ):
        """
        Initialize commit manager.
        :param watchlist: Watchlist manager.
        :param ai: AI manager.
        :param decoder_settings: Decoder settings.
        :param qdrant: Qdrant manager.
        """
        self.watchlist = watchlist
        self.ai = ai
        self.decoder_settings = decoder_settings
        self.qdrant = qdrant

    def commit(self) -> None:
        """
        Commit all tracked files.
        """
        # Added files
        added_files = self.watchlist.diff_filter(self.watchlist.DIFF_ADDED)
        if len(added_files) == 0:
            logger.info(f"No added files to commit")
        else:
            logger.info(f"Committing ({len(added_files)}) added file(s)...")
            self.commit_diff(added_files)

        # Changed files
        changed_files = self.watchlist.diff_filter(self.watchlist.DIFF_CHANGED)
        if len(changed_files) == 0:
            logger.info(f"No changed files to commit")
        else:
            logger.info(f"Committing ({len(changed_files)}) changed file(s)...")
            self.commit_diff(changed_files)

        # Removed files
        removed_files = self.watchlist.diff_filter(self.watchlist.DIFF_REMOVED)
        if len(removed_files) == 0:
            logger.info(f"No removed files to commit")
        else:
            logger.info(f"Committing ({len(removed_files)}) removed file(s)...")

            confirm = typer.confirm(
                f"You are about to remove any data associated with ({len(removed_files)}) untracked file(s) "
                f"from the Qdrant database. Are you sure?"
            )
            if not confirm:
                logger.warning(f"({len(removed_files)}) untracked file(s) remain in the Qdrant database")
            else:
                self.commit_diff(removed_files)

    def commit_diff(self, tracked_files: FilteredFiles) -> None:
        """
        Commit tracked files.
        :param tracked_files: Tracked files.
        """
        tracked_file_data = [
            FileData(ai=self.ai, decoder_settings=self.decoder_settings, file_path=file_path, file_meta=file_meta)
            for file_path, file_meta in tracked_files.items()
        ]

        tracked_unprocessable = [file_data for file_data in tracked_file_data if not file_data.is_processable()]
        tracked_processable = [file_data for file_data in tracked_file_data if file_data.is_processable()]

        for file_data in tracked_unprocessable:
            logger.warning(f"IGNORING unprocessable {format_file(file_data.file_path)}")
            if file_data.file_meta['diff'] == self.watchlist.DIFF_REMOVED:
                _success = self.qdrant.remove(file_data)
                self.watchlist.diff_mark_resolved(file_data)

        for file_data in tracked_processable:
            match file_data.file_meta['diff']:
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
                    logger.error(f"Invalid diff option: '{file_data.file_meta['diff']}'")
                    raise typer.Exit(code=1)
