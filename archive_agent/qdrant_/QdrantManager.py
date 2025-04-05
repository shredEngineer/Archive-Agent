#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from typing import List

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
from archive_agent.data import ChunkManager
from archive_agent.data import FileData
from archive_agent.util import CliManager
from archive_agent.util.format import format_time, format_file

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
        chunker: ChunkManager,
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
        :param chunker: Chunk manager.
        :param server_url: Server URL.
        :param collection: Collection name.
        :param vector_size: Vector size.
        :param score_min: Minimum score of retrieved chunks (`0`...`1`).
        :param chunks_max: Maximum number of retrieved chunks
        """
        self.cli = cli
        self.openai = openai
        self.chunker = chunker
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

    def add(self, file_path: str, file_mtime: float, quiet: bool = False) -> bool:
        """
        Add file to Qdrant collection.
        :param file_path: File path.
        :param file_mtime: File modification time.
        :param quiet: Quiet output if True.
        :return: True if successful, False otherwise. 
        """
        if not quiet:
            logger.info(f" - Adding {format_file(file_path)}")

        data = FileData(openai=self.openai, chunker=self.chunker, file_path=file_path, file_mtime=file_mtime)
        data.process()
        
        if len(data.points) == 0:
            logger.warning(f"Skipping empty file")
            return False

        try:
            self.qdrant.upsert(collection_name=self.collection, points=data.points)
        except UnexpectedResponse as e:
            logger.error(f"Qdrant add failed: '{e}'")
            return False

        logger.info(f" - ({len(data.points)}) vectors added")
        return True

    def remove(self, file_path: str, quiet: bool = False) -> bool:
        """
        Remove file from Qdrant collection.
        :param file_path: File path.
        :param quiet: Quiet output if True.
        :return: True if successful, False otherwise.
        """
        logger.debug(f" - Counting chunks for {format_file(file_path)}")

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
                logger.warning(f" - No chunks found for {format_file(file_path)}")
            return True

        if not quiet:
            logger.info(f" - Removing ({count}) chunk(s) of {format_file(file_path)}")

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
        logger.info(f" - Changing {format_file(file_path)}")

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

    def query(self, question: str) -> str:
        """
        Get answer to question using RAG.
        :param question: Question.
        :return: Answer.
        """
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
                f"<<< file://{point.payload['file_path']} @ {format_time(point.payload['file_mtime'])} >>>",
                f"{point.payload['chunk']}\n",
            ])
            for point in response.points
        ])

        answer = self.openai.query(question, context)
        return answer
