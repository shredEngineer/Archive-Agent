#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from qdrant_client import QdrantClient
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

    def add(self, file_path: str, file_mtime: float, quiet: bool = False) -> None:
        """
        Add file to Qdrant collection.
        :param file_path: File path.
        :param file_mtime: File modification time.
        :param quiet: Quiet output if True.
        """
        if not quiet:
            logger.info(f" - Adding file: '{file_path}'")

        data = FileData(openai=self.openai, chunker=self.chunker, file_path=file_path, file_mtime=file_mtime)
        data.process()

        self.qdrant.upsert(collection_name=self.collection, points=data.points)

        logger.info(f" - ({len(data.points)}) vectors added")

    def remove(self, file_path: str, quiet: bool = False) -> None:
        """
        Remove file from Qdrant collection.
        :param file_path: File path.
        :param quiet: Quiet output if True.
        """
        if not quiet:
            logger.info(f" - Removing file: '{file_path}'")

        self.qdrant.delete(
            collection_name=self.collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key='file_path',
                            match=MatchValue(value=file_path),
                        )
                    ]
                )
            ),
        )

    def change(self, file_path: str, file_mtime: float) -> None:
        """
        Change file in Qdrant collection.
        :param file_path: File path.
        :param file_mtime: File modification time.
        """
        logger.info(f" - Changing file: '{file_path}'")

        self.remove(file_path, quiet=True)
        self.add(file_path, file_mtime, quiet=True)

    def search(self, question: str) -> List[ScoredPoint]:
        """
        Get points matching the question.
        :param question: Question.
        :return: Points.
        """
        vector = self.openai.embed(question)

        response = self.qdrant.query_points(
            collection_name=self.collection,
            query=vector,
            score_threshold=self.score_min,
            limit=self.chunks_max,
            with_payload=True,
        )

        self.cli.format_points(response.points)
        return response.points

    def query(self, question: str) -> str:
        """
        Get answer to question using RAG.
        :param question: Question.
        :return: Answer.
        """
        vector = self.openai.embed(question)

        response = self.qdrant.query_points(
            collection_name=self.collection,
            query=vector,
            score_threshold=self.score_min,
            limit=self.chunks_max,
            with_payload=True,
        )

        self.cli.format_points(response.points)

        context = "\n\n\n\n".join([
            "\n\n".join([
                f"<<<{point.payload['file_path']}>>>",
                f"{point.payload['chunk']}\n",
            ])
            for point in response.points
        ])

        answer = self.openai.query(question, context)
        return answer
