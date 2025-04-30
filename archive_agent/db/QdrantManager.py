#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from typing import List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    VectorParams,
    Distance,
    Filter,
    FilterSelector,
    FieldCondition,
    MatchValue,
    ScoredPoint,
)

from archive_agent.ai.AiManager import AiManager
from archive_agent.data.FileData import FileData
from archive_agent.util.CliManager import CliManager
from archive_agent.util.format import format_time, format_file
from archive_agent.ai_schema.QuerySchema import QuerySchema

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)


class QdrantManager:
    """
    Qdrant manager.
    """

    def __init__(
        self,
        cli: CliManager,
        ai: AiManager,
        server_url: str,
        collection: str,
        vector_size: int,
        score_min: float,
        chunks_max: int,
    ):
        """
        Initialize Qdrant manager.
        :param cli: CLI manager.
        :param ai: AI manager.
        :param server_url: Server URL.
        :param collection: Collection name.
        :param vector_size: Vector size.
        :param score_min: Minimum score of retrieved chunks (`0`...`1`).
        :param chunks_max: Maximum number of retrieved chunks
        """
        self.cli = cli
        self.ai = ai
        self.qdrant = QdrantClient(url=server_url)
        self.collection = collection
        self.vector_size = vector_size
        self.score_min = score_min
        self.chunks_max = chunks_max

        if not self.qdrant.collection_exists(collection):
            logger.info(f"Creating new Qdrant collection: '{collection}' (vector size: {vector_size})")
            self.qdrant.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            logger.info(f"Connected to Qdrant collection: '{collection}'")

    def add(self, file_data: FileData, quiet: bool = False) -> bool:
        """
        Add file to Qdrant collection.
        :param file_data: File data.
        :param quiet: Quiet output if True.
        :return: True if successful, False otherwise.
        """
        if not quiet:
            logger.info(f"- ADDING {format_file(file_data.file_path)}")

        if not file_data.process():
            logger.warning(f"Failed to add file")
            return False

        if len(file_data.points) == 0:
            logger.warning(f"Failed to add EMPTY file")
            return False

        partial_size = 100
        num_points_added = 0
        total_points = len(file_data.points)
        for i in range(0, total_points, partial_size):
            points_partial = file_data.points[i:i + partial_size]
            logger.info(f"Adding vector(s) [{i + 1} : {i + len(points_partial)}] / ({total_points})")
            try:
                self.qdrant.upsert(collection_name=self.collection, points=points_partial)
            except UnexpectedResponse as e:
                logger.exception(f"Qdrant add failed: {e}")
                return False
            num_points_added += len(points_partial)

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
            count_result = self.qdrant.count(
                collection_name=self.collection,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key='file_path',
                            match=MatchValue(value=file_data.file_path),
                        ),
                    ],
                ),
                exact=True,
            )
            count = count_result.count
        except UnexpectedResponse as e:
            logger.exception(f"Qdrant count failed: {e}")
            return False

        if count == 0:
            if not quiet:
                logger.info(f"No chunks to remove for {format_file(file_data.file_path)}")
            return True

        if not quiet:
            logger.info(f"- REMOVING ({count}) chunk(s) of {format_file(file_data.file_path)}")

        try:
            self.qdrant.delete(
                collection_name=self.collection,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key='file_path',
                                match=MatchValue(value=file_data.file_path),
                            ),
                        ],
                    ),
                ),
            )
        except UnexpectedResponse as e:
            logger.exception(f"Qdrant delete failed: {e}")
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
        Get points relevant to the question.
        :param question: Question.
        :return: Points.
        """
        self.cli.format_question(question)

        vector = self.ai.embed(question)

        try:
            response = self.qdrant.query_points(
                collection_name=self.collection,
                query=vector,
                score_threshold=self.score_min,
                limit=self.chunks_max,
                with_payload=True,
            )
        except UnexpectedResponse as e:
            logger.exception(f"Qdrant query failed: {e}")
            raise typer.Exit(code=1)

        self.cli.format_points(response.points)
        return response.points

    def query(self, question: str) -> Tuple[QuerySchema, str]:
        """
        Get answer to question using RAG.
        :param question: Question.
        :return: (QuerySchema, formatted answer)
        """
        self.cli.format_question(question)

        vector = self.ai.embed(question)

        try:
            response = self.qdrant.query_points(
                collection_name=self.collection,
                query=vector,
                score_threshold=self.score_min,
                limit=self.chunks_max,
                with_payload=True,
            )
        except UnexpectedResponse as e:
            logger.exception(f"Qdrant query failed: {e}")
            raise typer.Exit(code=1)

        self.cli.format_points(response.points)

        context = "\n\n\n\n".join([
            "\n\n".join([
                f"<<< "
                f"Chunk ({point.payload['chunk_index'] + 1}) / ({point.payload['chunks_total']}) "
                f"of {format_file(point.payload['file_path'])} "
                f"@ {format_time(point.payload['file_mtime'])} "
                f">>>",
                f"{point.payload['chunk_text']}\n",
            ])
            for point in response.points
            if point.payload is not None  # makes pyright happy
        ])

        query_result = self.ai.query(question, context)
        if query_result.reject:
            logger.warning(f"Query rejected: {query_result.rejection_reason}")

        answer_text = self.cli.format_answer(query_result)

        return query_result, answer_text
