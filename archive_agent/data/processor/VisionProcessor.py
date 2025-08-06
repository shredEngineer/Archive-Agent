# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import concurrent.futures
from dataclasses import dataclass
from typing import List, Union, Optional, Callable, Any
import io
from logging import Logger

from PIL import Image
from rich.progress import Progress

from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.data.loader.image import ImageToTextCallback
from archive_agent.util.text_util import splitlines_exact


@dataclass
class VisionRequest:
    """
    Vision processing request containing image data, callback, and formatting logic.
    """
    image_data: Union[bytes, Image.Image]  # Support both PDF bytes and PIL Images
    callback: ImageToTextCallback          # The actual callback to use
    formatter: Callable[[Optional[str]], str]  # Lambda for conditional formatting
    log_header: str                       # Pre-built log message for progress
    image_index: int                      # For logging context
    page_index: int                       # For reassembly into per-page structure


class VisionProcessor:
    """
    Unified vision processor for parallel image-to-text processing.
    Handles both PDF and Binary document vision requests.
    """

    def __init__(self, ai_factory: AiManagerFactory, logger: Logger, verbose: bool, file_path: str, max_workers: int):
        """
        Initialize vision processor.
        :param ai_factory: AI manager factory for creating worker instances.
        :param logger: Logger instance from ai.cli hierarchy.
        :param verbose: Enable verbose output.
        :param file_path: File path for logging context.
        :param max_workers: Max. workers.
        """
        self.ai_factory = ai_factory
        self.logger = logger
        self.verbose = verbose
        self.file_path = file_path
        self.max_workers = max_workers

    def process_vision_requests_parallel(
            self,
            requests: List[VisionRequest],
            progress: Optional[Progress] = None,
            task_id: Optional[Any] = None
    ) -> List[str]:
        """
        Process vision requests in parallel with progress tracking.
        :param requests: List of VisionRequest objects to process.
        :param progress: A rich.progress.Progress object for progress reporting.
        :param task_id: The task ID for the progress bar.
        :return: List of formatted result strings in same order as requests.
        """
        if not requests:
            return []

        def process_vision_request(request_data: tuple) -> tuple:
            request_index, request = request_data
            try:
                if self.verbose:
                    self.logger.info(request.log_header)

                # Create dedicated AI manager for this vision request
                ai_worker = self.ai_factory.get_ai()
                # Convert bytes to PIL Image if needed
                if isinstance(request.image_data, bytes):
                    with Image.open(io.BytesIO(request.image_data)) as image:
                        vision_result = request.callback(ai_worker, image)
                else:
                    # Already PIL Image
                    vision_result = request.callback(ai_worker, request.image_data)

                # Validate single-line constraint before formatting (same as original)
                if vision_result is not None:
                    assert len(splitlines_exact(vision_result)) == 1, f"Text from image must be single line:\n'{vision_result}'"

                # Apply formatter to get final result
                _formatted_result = request.formatter(vision_result)

                # Update progress after successful vision processing
                if progress and task_id:
                    progress.update(task_id, advance=1)

                return request_index, _formatted_result

            except Exception as e:
                self.logger.error(f"Failed to process vision request ({request.image_index + 1}): {e}")
                # Apply formatter to None for error case
                _formatted_result = request.formatter(None)

                # Update progress even on failure
                if progress and task_id:
                    progress.update(task_id, advance=1)

                return request_index, _formatted_result

        # Use ThreadPoolExecutor for parallel vision processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all vision tasks
            future_to_request = {
                executor.submit(process_vision_request, (request_index, request)): (request_index, request)
                for request_index, request in enumerate(requests)
            }

            # Collect results in original order
            results_dict = {}
            for future in concurrent.futures.as_completed(future_to_request):
                request_index, original_request = future_to_request[future]
                try:
                    result_index, formatted_result = future.result()
                    results_dict[result_index] = formatted_result
                except Exception as exc:
                    self.logger.error(f"Vision request ({request_index + 1}) generated an exception: {exc}")
                    # Apply formatter to None for exception case
                    formatted_result = original_request.formatter(None)
                    results_dict[request_index] = formatted_result

            # Return results in original order
            return [results_dict[i] for i in range(len(requests))]
