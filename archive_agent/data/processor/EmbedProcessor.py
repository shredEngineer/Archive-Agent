# TODO: Implement graceful shutdown of threads.

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import concurrent.futures
from typing import List, Any, Optional, Tuple

import typer
from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.ai_provider.AiProviderError import AiProviderMaxTokensError
from archive_agent.util.format import format_file
from archive_agent.core.ProgressManager import ProgressInfo


class EmbedProcessor:
    """
    Handles parallel processing of chunk embeddings.
    """

    def __init__(self, ai_factory: AiManagerFactory, logger, file_path: str, max_workers: int):
        """
        Initialize chunk embedding processor.
        :param ai_factory: AI manager factory for creating worker instances.
        :param logger: Logger instance.
        :param file_path: File path for logging.
        :param max_workers: Max. workers.
        """
        self.ai_factory = ai_factory
        self.logger = logger
        self.file_path = file_path
        self.max_workers = max_workers

    def process_chunks_parallel(
            self,
            chunks: List[Any],
            verbose: bool,
            progress_info: ProgressInfo
    ) -> List[Tuple[Any, Optional[List[float]]]]:
        """
        Process chunks in parallel for embedding.
        :param chunks: List of chunks to process.
        :param verbose: Whether to log verbose messages.
        :param progress_info: Progress tracking information
        :return: List of (chunk, vector) tuples in original order.
        """
        def embed_chunk(chunk_data: Tuple[int, Any]) -> Tuple[int, Any, Optional[List[float]]]:
            chunk_index, chunk = chunk_data
            try:
                if verbose:
                    self.logger.info(
                        f"Processing chunk ({chunk_index + 1}) / ({len(chunks)}) "
                        f"of {format_file(self.file_path)}"
                    )

                assert chunk.reference_range != (0, 0), "Invalid chunk reference range (WTF, please report)"

                # Create dedicated AI manager for this embedding
                ai_worker = self.ai_factory.get_ai()
                _vector = ai_worker.embed(text=chunk.text)

                # Update progress after successful embedding
                progress_info.progress_manager.update_task(progress_info.parent_key, advance=1)

                return chunk_index, chunk, _vector
            except typer.Exit:
                raise  # Network retries exhausted — don't swallow process exit
            except AiProviderMaxTokensError as e:
                self.logger.warning(f"Embedding chunk ({chunk_index + 1}) skipped — max tokens exceeded: {e}")
                progress_info.progress_manager.update_task(progress_info.parent_key, advance=1)
                return chunk_index, chunk, None
            except Exception as e:
                self.logger.error(f"Failed to embed chunk ({chunk_index + 1}): {e}")
                progress_info.progress_manager.update_task(progress_info.parent_key, advance=1)
                return chunk_index, chunk, None

        # Use ThreadPoolExecutor for parallel embedding
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all embedding tasks
            future_to_chunk = {
                executor.submit(embed_chunk, (chunk_index, chunk)): (chunk_index, chunk)
                for chunk_index, chunk in enumerate(chunks)
            }

            # Collect results in original order
            results_dict = {}
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_index, original_chunk = future_to_chunk[future]
                try:
                    result_index, chunk, vector = future.result()
                    results_dict[result_index] = (chunk, vector)
                except typer.Exit:
                    raise  # Network retries exhausted — don't swallow process exit
                except AiProviderMaxTokensError as exc:
                    self.logger.warning(f"Chunk ({chunk_index + 1}) skipped — max tokens exceeded: {exc}")
                    results_dict[chunk_index] = (original_chunk, None)
                except Exception as exc:
                    self.logger.error(f"Chunk ({chunk_index + 1}) generated an exception: {exc}")
                    results_dict[chunk_index] = (original_chunk, None)

            # Return results in original order
            return [results_dict[i] for i in range(len(chunks))]
