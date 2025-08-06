# archive_agent/db/QdrantManager.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from typing import List, Tuple, Dict
import sys
import json

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    Filter,
    FilterSelector,
    FieldCondition,
    MatchValue,
    MatchAny,
    ScoredPoint,
)

from archive_agent.ai.AiManager import AiManager
from archive_agent.ai.query.AiQuery import AiQuery, QuerySchema
from archive_agent.data.FileData import FileData
from archive_agent.core.CliManager import CliManager
from archive_agent.util.format import format_file
from archive_agent.db.QdrantSchema import parse_payload
from archive_agent.util.RetryManager import RetryManager

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)


class QdrantManager:
    """
    Qdrant manager.
    """

    QDRANT_REQUEST_TIMEOUT_S = 3600
    QDRANT_UPSERT_BATCH_SIZE = 25
    QDRANT_RETRY_KWARGS = dict(
        delay_min=1.0,
        delay_max=10.0,
        backoff_exponent=2,
        retries=3,
    )

    def __init__(
            self,
            cli: CliManager,
            ai: AiManager,
            server_url: str,
            collection: str,
            vector_size: int,
            retrieve_score_min: float,
            retrieve_chunks_max: int,
            rerank_chunks_max: int,
            expand_chunks_radius: int,
    ):
        """
        Initialize Qdrant manager.
        :param cli: CLI manager.
        :param ai: AI manager.
        :param server_url: Server URL.
        :param collection: Collection name.
        :param vector_size: Vector size.
        :param retrieve_score_min: Minimum score of retrieved chunks (`0`...`1`).
        :param retrieve_chunks_max: Maximum number of retrieved chunks.
        :param rerank_chunks_max: Number of top chunks to keep after reranking.
        :param expand_chunks_radius: Number of preceding and following chunks to prepend and append to each reranked chunk.
        """
        self.cli = cli
        self.ai = ai
        self.qdrant = QdrantClient(
            url=server_url,
            timeout=QdrantManager.QDRANT_REQUEST_TIMEOUT_S,
        )
        self.collection = collection
        self.vector_size = vector_size
        self.retrieve_score_min = retrieve_score_min
        self.retrieve_chunks_max = retrieve_chunks_max
        self.rerank_chunks_max = rerank_chunks_max
        self.expand_chunks_radius = expand_chunks_radius

        self.retry_manager = RetryManager(**QdrantManager.QDRANT_RETRY_KWARGS)

        try:
            exists = self.retry_manager.retry(
                func=self.qdrant.collection_exists,
                kwargs={"collection_name": collection}
            )
            if not exists:
                logger.info(f"Creating new Qdrant collection: '{collection}' (vector size: {vector_size})")
                self.retry_manager.retry(
                    func=self.qdrant.create_collection,
                    kwargs={
                        "collection_name": collection,
                        "vectors_config": VectorParams(size=vector_size, distance=Distance.COSINE),
                    }
                )
            else:
                logger.info(f"Connected to Qdrant collection: '{collection}'")
        except Exception as e:
            logger.error(
                f"Failed to connect to Qdrant collection: {e}\n"
                f"Make sure the Qdrant server is running ('./manage-qdrant.sh start')"
            )
            raise typer.Exit(code=1)

    def add(self, file_data: FileData, quiet: bool = False) -> bool:
        """
        Add file to Qdrant collection.
        :param file_data: File data.
        :param quiet: Quiet output if True.
        :return: True if successful, False otherwise.
        """
        if not quiet:
            logger.info(f"- ADDING {format_file(file_data.file_path)}")

        if len(file_data.points) == 0:
            logger.warning(f"Failed to add EMPTY file")
            return False

        num_points_added = 0
        total_points = len(file_data.points)
        for i in range(0, total_points, QdrantManager.QDRANT_UPSERT_BATCH_SIZE):

            points_batch = file_data.points[i:i + QdrantManager.QDRANT_UPSERT_BATCH_SIZE]

            payload_json = json.dumps([p.model_dump() for p in points_batch])
            payload_bytes = sys.getsizeof(payload_json)

            logger.info(
                f"Adding vector(s) [{i + 1} : {i + len(points_batch)}] / ({total_points}), "
                f"estimated payload size: {payload_bytes / (1024 * 1024):.2f} MiB"
            )

            try:
                self.retry_manager.retry(
                    func=self.qdrant.upsert,
                    kwargs={
                        "collection_name": self.collection,
                        "points": points_batch
                    }
                )
            except Exception as e:
                logger.exception(f"Qdrant add failed after retries: {e}")
                return False

            num_points_added += len(points_batch)

        logger.info(f"({len(file_data.points)}) vector(s) added")
        return True

    def remove(self, file_data: FileData, quiet: bool = False) -> bool:
        """
        Remove file from Qdrant collection.
        :param file_data: File data.
        :param quiet: Quiet output if True.
        :return: True if successful, False otherwise.
        """
        logger.debug(f"Counting chunks for {format_file(file_data.file_path)}")

        try:
            count_result = self.retry_manager.retry(
                func=self.qdrant.count,
                kwargs={
                    "collection_name": self.collection,
                    "count_filter": Filter(
                        must=[
                            FieldCondition(
                                key='file_path',
                                match=MatchValue(value=file_data.file_path),
                            ),
                        ],
                    ),
                    "exact": True,
                }
            )
            count = count_result.count
        except Exception as e:
            logger.exception(f"Qdrant count failed after retries: {e}")
            return False

        if count == 0:
            if not quiet:
                logger.info(f"- NO CHUNKS to remove for {format_file(file_data.file_path)}")
            return True

        if not quiet:
            logger.info(f"- REMOVING ({count}) chunk(s) of {format_file(file_data.file_path)}")

        try:
            self.retry_manager.retry(
                func=self.qdrant.delete,
                kwargs={
                    "collection_name": self.collection,
                    "points_selector": FilterSelector(
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key='file_path',
                                    match=MatchValue(value=file_data.file_path),
                                ),
                            ],
                        ),
                    ),
                }
            )
        except Exception as e:
            logger.exception(f"Qdrant delete failed after retries: {e}")
            return False

        return True

    def change(self, file_data: FileData) -> bool:
        """
        Change file in Qdrant collection.
        :param file_data: File data.
        :return: True if successful, False otherwise.
        """
        logger.info(f"- CHANGING {format_file(file_data.file_path)}")

        successful_remove = self.remove(file_data, quiet=True)
        if not successful_remove:
            return False

        successful_add = self.add(file_data, quiet=True)
        if not successful_add:
            return False

        return True

    def search(self, question: str) -> List[ScoredPoint]:
        """
        Get reranked points relevant to the question.
        :param question: Question.
        :return: Reranked points.
        """
        self.cli.format_question(question)

        vector = self.ai.embed(question)

        try:
            response = self.retry_manager.retry(
                func=self.qdrant.query_points,
                kwargs={
                    "collection_name": self.collection,
                    "query": vector,
                    "score_threshold": self.retrieve_score_min,
                    "limit": self.retrieve_chunks_max,
                    "with_payload": True,
                }
            )
        except Exception as e:
            logger.exception(f"Qdrant query failed after retries: {e}")
            raise typer.Exit(code=1)

        points = response.points

        self.cli.format_retrieved_points(points)

        if len(points) > 1:  # Rerank points

            indexed_chunks = {
                index: parse_payload(point.payload).chunk_text
                for index, point in enumerate(points)
            }

            reranked_schema = self.ai.rerank(question=question, indexed_chunks=indexed_chunks)

            if not reranked_schema.is_rejected:
                reranked_indices = reranked_schema.reranked_indices
            else:
                reranked_indices = range(len(points))  # Fallback

            if len(reranked_indices) > self.rerank_chunks_max:
                reranked_indices = reranked_indices[:self.rerank_chunks_max]

            points_reranked = []
            for index in reranked_indices:
                points_reranked.append(points[index])
            points = points_reranked

        self.cli.format_reranked_points(points)

        return points

    def _get_points(self, file_path: str, chunk_indices: List[int]) -> List[ScoredPoint]:
        """
        Get points with matching `file_path` and `chunk_index` in `chunk_indices`.
        :param file_path: File path.
        :param chunk_indices: Chunk indices.
        :return: Points.
        """
        if not chunk_indices:
            return []

        try:
            response = self.retry_manager.retry(
                func=self.qdrant.query_points,
                kwargs={
                    "collection_name": self.collection,
                    "query_filter": Filter(
                        must=[
                            FieldCondition(
                                key='file_path',
                                match=MatchValue(value=file_path),
                            ),
                            FieldCondition(
                                key='chunk_index',
                                match=MatchAny(any=chunk_indices),
                            ),
                        ],
                    ),
                    "with_payload": True,
                    "limit": len(chunk_indices),
                }
            )
        except Exception as e:
            logger.exception(f"Qdrant query failed after retries: {e}")
            raise typer.Exit(code=1)

        points = sorted(response.points, key=lambda point: parse_payload(point.payload).chunk_index)

        indices_found = {
            parse_payload(point.payload).chunk_index
            for point in points
        }
        indices_missing = set(chunk_indices) - indices_found
        if indices_missing:
            logger.critical(f"⚠️ Missing chunk(s) for {format_file(file_path)}: {sorted(indices_missing)}")

        return points

    def _expand_points(self, points: List[ScoredPoint]) -> List[ScoredPoint]:
        """
        Expand points by adding preceding and following chunks.
        :param points: Points to expand.
        :return: Expanded points.
        """
        points_expanded = []

        for point in points:
            model = parse_payload(point.payload)
            points_expanded.extend(
                self._get_points(
                    file_path=model.file_path,
                    chunk_indices=[
                        index for index in range(
                            max(0, model.chunk_index - self.expand_chunks_radius),
                            model.chunk_index
                        )
                    ],
                )
            )

            points_expanded.append(point)

            points_expanded.extend(
                self._get_points(
                    file_path=model.file_path,
                    chunk_indices=[
                        index for index in range(
                            model.chunk_index + 1,
                            min(
                                model.chunks_total,
                                model.chunk_index + self.expand_chunks_radius + 1
                            )
                        )
                    ],
                )
            )

        return points_expanded

    def _dedup_points(self, points: List[ScoredPoint]) -> List[ScoredPoint]:
        """
        Deduplicate points by file_path and chunk_index.
        :param points: Points to deduplicate.
        :return: Unique points.
        """
        unique_points = []
        seen = set()
        duplicates_by_file = {}
        for point in points:
            model = parse_payload(point.payload)
            key = (model.file_path, model.chunk_index)
            if key in seen:
                duplicates_by_file.setdefault(model.file_path, set()).add(model.chunk_index)
            else:
                seen.add(key)
                unique_points.append(point)

        if self.cli.VERBOSE_QUERY:
            for file_path, dups in duplicates_by_file.items():
                if dups:
                    logger.info(f"Deduplicated chunks for {format_file(file_path)}: {sorted(dups)}")

        return unique_points

    def query(self, question: str) -> Tuple[QuerySchema, str]:
        """
        Get answer to question using RAG.
        :param question: Question.
        :return: (QuerySchema, formatted answer)
        """
        points = self.search(question=question)

        if self.expand_chunks_radius > 0:  # Expand points
            points_expanded = self._expand_points(points)
            points = self._dedup_points(points_expanded)
            self.cli.format_expanded_deduped_points(points)

        query_result = self.ai.query(question, points)

        if query_result.is_rejected:
            logger.warning(f"⚠️ Query rejected: \"{query_result.rejection_reason}\"")

        answer_text = AiQuery.get_answer_text(query_result)

        self.cli.format_query(query_result=query_result, answer_text=answer_text)

        return query_result, answer_text

    def get_stats(self) -> Dict[str, int]:
        """
        Get stats, e.g. files and chunks counts.
        :return: Dict.
        """
        try:
            count_result = self.retry_manager.retry(
                func=self.qdrant.count,
                kwargs={
                    "collection_name": self.collection,
                    "count_filter": Filter(
                        must=[
                        ]
                    ),
                    "exact": True,
                }
            )

            # Get unique file paths using scroll with distinct field
            scroll_result = self.retry_manager.retry(
                func=self.qdrant.scroll,
                kwargs={
                    "collection_name": self.collection,
                    "scroll_filter": Filter(
                        must=[
                        ]
                    ),
                    "limit": 1_000_000_000,  # Large limit to get all points
                    "with_payload": True,
                }
            )

            unique_files = len({parse_payload(point.payload).file_path for point in scroll_result[0]})

        except Exception as e:
            logger.exception(f"Qdrant count failed after retries: {e}")
            raise typer.Exit(code=1)

        return {
            'chunks_count': count_result.count,
            'files_count': unique_files,
        }
