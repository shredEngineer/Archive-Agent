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

from archive_agent.openai_ import OpenAiManager
from archive_agent.data import FileData
from archive_agent.util import CliManager
from archive_agent.util.format import format_time, format_file
from archive_agent.openai_.OpenAiManager import QuerySchema

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)


class QdrantManager:
    """
    Qdrant manager.
    """

    def __init__(
        self,
        cli: CliManager,
        openai: OpenAiManager,
        server_url: str,
        collection: str,
        vector_size: int,
        score_min: float,
        chunks_max: int,
    ):
        """
        Initialize Qdrant manager.
        :param cli: CLI manager.
        :param openai: OpenAI manager.
        :param server_url: Server URL.
        :param collection: Collection name.
        :param vector_size: Vector size.
        :param score_min: Minimum score of retrieved chunks (`0`...`1`).
        :param chunks_max: Maximum number of retrieved chunks
        """
        self.cli = cli
        self.openai = openai
        self.qdrant = QdrantClient(url=server_url)
        self.collection = collection
        self.vector_size = vector_size
        self.score_min = score_min
        self.chunks_max = chunks_max

        if not self.qdrant.collection_exists(collection):
            logger.info(f"Creating new Qdrant collection: '{collection}'")
            self.qdrant.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            logger.info(f"Connected to Qdrant collection: '{collection}'")

    def add(self, file_path: str, file_mtime: float, quiet: bool = False) -> bool:
        """
        Add file to Qdrant collection.
        :param file_path: File path.
        :param file_mtime: File modification time.
        :param quiet: Quiet output if True.
        :return: True if successful, False otherwise.
        """
        if not quiet:
            logger.info(f"Adding {format_file(file_path)}")

        data = FileData(openai=self.openai, file_path=file_path, file_mtime=file_mtime)
        if not data.process():
            logger.warning(f"Failed to add file")
            return False

        if len(data.points) == 0:
            logger.warning(f"Failed to add empty file")
            return False

        try:
            self.qdrant.upsert(collection_name=self.collection, points=data.points)
        except UnexpectedResponse as e:
            logger.error(f"Qdrant add failed: '{e}'")
            return False

        logger.info(f"({len(data.points)}) vector(s) added")
        return True

    def remove(self, file_path: str, quiet: bool = False) -> bool:
        """
        Remove file from Qdrant collection.
        :param file_path: File path.
        :param quiet: Quiet output if True.
        :return: True if successful, False otherwise.
        """
        logger.debug(f"Counting chunks for {format_file(file_path)}")

        try:
            count_result = self.qdrant.count(
                collection_name=self.collection,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key='file_path',
                            match=MatchValue(value=file_path),
                        ),
                    ],
                ),
                exact=True,
            )
            count = count_result.count
        except UnexpectedResponse as e:
            logger.error(f"Qdrant count failed: '{e}'")
            return False

        if count == 0:
            if not quiet:
                logger.warning(f"No chunks found for {format_file(file_path)}")
            return True

        if not quiet:
            logger.info(f"Removing ({count}) chunk(s) of {format_file(file_path)}")

        try:
            self.qdrant.delete(
                collection_name=self.collection,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key='file_path',
                                match=MatchValue(value=file_path),
                            ),
                        ],
                    ),
                ),
            )
        except UnexpectedResponse as e:
            logger.error(f"Qdrant delete failed: '{e}'")
            return False

        return True

    def change(self, file_path: str, file_mtime: float) -> bool:
        """
        Change file in Qdrant collection.
        :param file_path: File path.
        :param file_mtime: File modification time.
        :return: True if successful, False otherwise.
        """
        logger.info(f"Changing {format_file(file_path)}")

        successful_remove = self.remove(file_path, quiet=True)
        if not successful_remove:
            return False

        successful_add = self.add(file_path, file_mtime, quiet=True)
        if not successful_add:
            return False

        return True

    def search(self, question: str) -> List[ScoredPoint]:
        """
        Get points matching the question.
        :param question: Question.
        :return: Points.
        """
        self.cli.format_question(question)

        vector = self.openai.embed(question)

        try:
            response = self.qdrant.query_points(
                collection_name=self.collection,
                query=vector,
                score_threshold=self.score_min,
                limit=self.chunks_max,
                with_payload=True,
            )
        except UnexpectedResponse as e:
            logger.error(f"Qdrant query failed: '{e}'")
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

        vector = self.openai.embed(question)

        try:
            response = self.qdrant.query_points(
                collection_name=self.collection,
                query=vector,
                score_threshold=self.score_min,
                limit=self.chunks_max,
                with_payload=True,
            )
        except UnexpectedResponse as e:
            logger.error(f"Qdrant query failed: '{e}'")
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

        query_result = self.openai.query(question, context)
        if query_result.reject:
            logger.warning(f"Query rejected: {query_result.rejection_reason}")

        answer_text = self.cli.format_answer(query_result)

        return query_result, answer_text
