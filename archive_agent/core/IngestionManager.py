# TODO: Implement graceful shutdown of threads.

#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import concurrent.futures
from typing import List, Tuple

from archive_agent.core.CliManager import CliManager
from archive_agent.data.FileData import FileData
from archive_agent.core.ProgressManager import ProgressInfo
from archive_agent.util.format import format_file, format_filename_short


class IngestionManager:
    """
    Ingestion manager for parallel file processing.
    """

    def __init__(self, cli: CliManager, progress_manager, max_workers):
        """
        Initialize ingestion manager.
        :param cli: CLI manager.
        :param progress_manager: Progress manager from ContextManager.
        :param max_workers: Max. workers.
        """
        self.cli = cli
        self.progress_manager = progress_manager
        self.max_workers = max_workers

    def process_files_parallel(
            self,
            files: List[FileData]
    ) -> List[Tuple[FileData, bool]]:
        """
        Process files in parallel with progress tracking.
        :param files: List of FileData objects to process.
        :return: List of (FileData, success) tuples.
        """
        if not files:
            return []

        processed_results = []
        with self.cli.progress_context(self.progress_manager) as (progress_manager, _):
            # Create overall files task as root of hierarchy
            overall_files_progress_key = progress_manager.start_task("Files", total=len(files))

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Create ProgressInfo for each file processing task
                overall_progress_info = progress_manager.create_progress_info(overall_files_progress_key)
                future_to_filedata = {
                    executor.submit(self._process_file_data, fd, overall_progress_info): fd
                    for fd in files
                }
                for future in concurrent.futures.as_completed(future_to_filedata):
                    file_data = future_to_filedata[future]
                    try:
                        processed_results.append(future.result())
                    except Exception as exc:
                        self.cli.logger.error(f"An exception occurred while processing {format_file(file_data.file_path)}: {exc}")
                        processed_results.append((file_data, False))

        return processed_results

    # noinspection PyMethodMayBeStatic
    def _process_file_data(
            self,
            file_data: FileData,
            overall_progress_info: ProgressInfo
    ) -> Tuple[FileData, bool]:
        """
        Wrapper to call file_data.process() and handle results for ThreadPoolExecutor, with progress reporting.

        THREAD SAFETY: This method is called by multiple worker threads concurrently.
        Each thread processes a different file, so file_progress_key values will be unique.
        The progress_manager must handle concurrent start_task/complete_task calls.
        """
        # Create individual file task as child of overall files task
        file_progress_key = overall_progress_info.progress_manager.start_task(
            format_filename_short(file_data.file_path),
            parent=overall_progress_info.parent_key
        )

        success = file_data.process(overall_progress_info.progress_manager, file_progress_key)
        overall_progress_info.progress_manager.complete_task(file_progress_key)

        return file_data, success
