#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import asyncio

import typer

from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.config.DecoderSettings import DecoderSettings
from archive_agent.core.CliManager import CliManager
from archive_agent.core.IngestionManager import IngestionManager
from archive_agent.core.lock import file_lock
from archive_agent.data.FileData import FileData
from archive_agent.db.QdrantManager import QdrantManager
from archive_agent.util.format import format_file
from archive_agent.watchlist.WatchlistManager import TrackedFiles, WatchlistManager


class CommitManager:
    """
    Commit manager.
    """

    def __init__(
            self,
            cli: CliManager,
            watchlist: WatchlistManager,
            ai_factory: AiManagerFactory,
            decoder_settings: DecoderSettings,
            qdrant: QdrantManager,
            progress_manager,
            max_workers_ingest: int,
            max_workers_vision: int,
            max_workers_embed: int,
    ):
        """
        Initialize commit manager.
        :param cli: CLI manager.
        :param watchlist: Watchlist manager.
        :param ai_factory: AI manager factory.
        :param decoder_settings: Decoder settings.
        :param qdrant: Qdrant manager.
        :param progress_manager: Progress manager from ContextManager.
        :param max_workers_ingest: Max. workers for IngestionManager.
        :param max_workers_vision: Max. workers for VisionProcessor.
        :param max_workers_embed: Max. workers for EmbedProcessor.
        """
        self.cli = cli
        self.watchlist = watchlist
        self.ai_factory = ai_factory
        self.decoder_settings = decoder_settings
        self.qdrant = qdrant
        self.progress_manager = progress_manager
        self.ingestion = IngestionManager(cli, progress_manager, max_workers=max_workers_ingest)
        self.max_workers_vision = max_workers_vision
        self.max_workers_embed = max_workers_embed

    @file_lock("archive_agent_watchlist")
    def commit(self, confirm_delete: bool) -> None:
        """
        Commit all tracked files.
        :param confirm_delete: Automatically confirm deleting untracked files from the database.
        """
        # Added files
        added_files = self.watchlist.get_diff_files(self.watchlist.DIFF_ADDED)
        if len(added_files) == 0:
            self.cli.logger.info(f"No added files to commit")
        else:
            self.cli.logger.info(f"Committing ({len(added_files)}) added file(s)...")
            self.cli.logger.info(f"⌛ Preparing documents for ingestion...please stand by")
            self.commit_diff(added_files)

        # Changed files
        changed_files = self.watchlist.get_diff_files(self.watchlist.DIFF_CHANGED)
        if len(changed_files) == 0:
            self.cli.logger.info(f"No changed files to commit")
        else:
            self.cli.logger.info(f"Committing ({len(changed_files)}) changed file(s)...")
            self.cli.logger.info(f"⌛ Preparing documents for ingestion...please stand by")
            self.commit_diff(changed_files)

        # Removed files
        removed_files = self.watchlist.get_diff_files(self.watchlist.DIFF_REMOVED)
        if len(removed_files) == 0:
            self.cli.logger.info(f"No removed files to commit")
        else:
            self.cli.logger.info(f"Committing ({len(removed_files)}) removed file(s)...")

            for file in removed_files.keys():
                self.cli.logger.info(f"- TO BE REMOVED  {format_file(file)}")

            if confirm_delete:
                self.cli.logger.warning(
                    f"Removing any data associated with "
                    f"({len(removed_files)}) untracked file(s) "
                    f"from the Qdrant database."
                )
                confirm = True
            else:
                self.cli.logger.warning(
                    f"You are about to remove any data associated with "
                    f"({len(removed_files)}) untracked file(s) "
                    f"from the Qdrant database."
                )
                confirm = typer.confirm(
                    f"👉 Delete files from the Qdrant database?"
                )
            if not confirm:
                self.cli.logger.warning(f"({len(removed_files)}) untracked file(s) remain in the Qdrant database")
            else:
                self.commit_diff(removed_files)

        if len(added_files) > 0 or len(changed_files) > 0 or len(removed_files) > 0:
            self.cli.logger.info(f"✅ Commit completed:")
            self.cli.logger.info(f"- ({len(added_files)}) file(s) added to Qdrant database")
            self.cli.logger.info(f"- ({len(changed_files)}) file(s) updated in Qdrant database")
            self.cli.logger.info(f"- ({len(removed_files)}) file(s) removed from Qdrant database")

    def commit_diff(self, tracked_files: TrackedFiles) -> None:
        """
        Commit tracked files.
        :param tracked_files: Tracked files.
        """
        tracked_file_data = []

        # Populate list of file data objects, each with AI factory for parallel processing.
        for file_path, file_meta in tracked_files.items():
            file_data = FileData(
                ai_factory=self.ai_factory,
                decoder_settings=self.decoder_settings,
                file_path=file_path,
                file_meta=file_meta,
                max_workers_vision=self.max_workers_vision,
                max_workers_embed=self.max_workers_embed,
            )
            tracked_file_data.append(file_data)

        tracked_unprocessable = [file_data for file_data in tracked_file_data if not file_data.is_processable()]
        tracked_processable = [file_data for file_data in tracked_file_data if file_data.is_processable()]

        for file_data in tracked_unprocessable:
            self.cli.logger.warning(f"IGNORING unprocessable {format_file(file_data.file_path)}")
            if file_data.file_meta['diff'] == self.watchlist.DIFF_REMOVED:
                _success = asyncio.run(self.qdrant.remove(file_data))
                self.watchlist.diff_mark_resolved(file_data)

        files_to_process_in_parallel = [
            fd for fd in tracked_processable if fd.file_meta['diff'] in [self.watchlist.DIFF_ADDED, self.watchlist.DIFF_CHANGED]
        ]
        files_to_process_sequentially = [
            fd for fd in tracked_processable if fd.file_meta['diff'] == self.watchlist.DIFF_REMOVED
        ]

        processed_results = self.ingestion.process_files_parallel(files_to_process_in_parallel)

        for file_data, success in processed_results:
            if not success:
                self.cli.logger.warning(f"Failed to process {format_file(file_data.file_path)}")
                continue

            if file_data.file_meta['diff'] == self.watchlist.DIFF_ADDED:
                if asyncio.run(self.qdrant.add(file_data)):
                    self.watchlist.diff_mark_resolved(file_data)
            elif file_data.file_meta['diff'] == self.watchlist.DIFF_CHANGED:
                if asyncio.run(self.qdrant.change(file_data)):
                    self.watchlist.diff_mark_resolved(file_data)

        for file_data in files_to_process_sequentially:
            if asyncio.run(self.qdrant.remove(file_data)):
                self.watchlist.diff_mark_resolved(file_data)
