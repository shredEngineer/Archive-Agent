#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import concurrent.futures
from typing import List, Tuple, Optional, Any

from rich.progress import Progress

from archive_agent.core.CliManager import CliManager
from archive_agent.data.FileData import FileData
from archive_agent.util.format import format_file, format_filename_short


class IngestionManager:
    """
    Ingestion manager for parallel file processing.
    """

    def __init__(self, cli: CliManager, max_workers):
        """
        Initialize ingestion manager.
        :param cli: CLI manager.
        :param max_workers: Max. workers.
        """
        self.cli = cli
        self.max_workers = max_workers

    def process_files_parallel(
            self,
            files: List[FileData],
            progress_label: str = "Files"
    ) -> List[Tuple[FileData, bool]]:
        """
        Process files in parallel with progress tracking.
        :param files: List of FileData objects to process.
        :param progress_label: Label for progress display.
        :return: List of (FileData, success) tuples.
        """
        if not files:
            return []

        processed_results = []
        with self.cli.progress_context(progress_label, total=len(files)) as (progress, overall_task_id):
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_filedata = {
                    executor.submit(self._process_file_data, fd, progress, overall_task_id): fd
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
            progress: Optional[Progress] = None,
            overall_task_id: Optional[Any] = None
    ) -> Tuple[FileData, bool]:
        """
        Wrapper to call file_data.process() and handle results for ThreadPoolExecutor, with progress reporting.
        """
        task_id = None
        if progress:
            # Determine total phases: Vision (if supported) + Chunking + Embedding
            from archive_agent.data.loader.pdf import is_pdf_document
            from archive_agent.data.loader.text import is_binary_document
            has_vision = is_pdf_document(file_data.file_path) or is_binary_document(file_data.file_path)
            total_phases = 3 if has_vision else 2
            task_id = progress.add_task(f"{format_filename_short(file_data.file_path)}", total=total_phases, start=True)

        success = file_data.process(progress, task_id)

        if progress and task_id is not None:
            progress.remove_task(task_id)
            if overall_task_id is not None:
                progress.update(overall_task_id, advance=1)

        return file_data, success
