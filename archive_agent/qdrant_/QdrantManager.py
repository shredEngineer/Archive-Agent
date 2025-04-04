#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from rich import print
from rich.panel import Panel
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

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)


class QdrantManager:
    """
    Qdrant manager.
    """

    def __init__(
        self,
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
        :param openai: OpenAI manager.
        :param chunker: Chunk manager.
        :param server_url: Server URL.
        :param collection: Collection name.
        :param vector_size: Vector size.
        :param score_min: Minimum score of retrieved chunks (`0`...`1`).
        :param chunks_max: Maximum number of retrieved chunks
        """
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

    def add(self, file_path: str, file_mtime: float) -> None:
        """
        Add file to Qdrant collection.
        :param file_path: File path.
        :param file_mtime: File modification time.
        """
        logger.info(f"Adding file: '{file_path}'")

        data = FileData(openai=self.openai, chunker=self.chunker, file_path=file_path, file_mtime=file_mtime)
        data.process()

        self.qdrant.upsert(collection_name=self.collection, points=data.points)

        logger.info(f" - ({len(data.points)}) vectors added")

    def remove(self, file_path: str) -> None:
        """
        Remove file from Qdrant collection.
        :param file_path: File path.
        """
        logger.info(f"Removing file: '{file_path}'")

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
        logger.info(f"Changing file (removing and adding): '{file_path}'")

        self.remove(file_path)
        self.add(file_path, file_mtime)

    def search(self, question: str) -> None:
        """
        List files matching the question.
        :param question: Question.
        """
        logger.info(f"Searching:")
        print(Panel(f"[red]{question}"))

        logger.info(f" - Embedding question...")
        total_tokens, vector = self.openai.embed(question)
        logger.info(f"   - Used ({total_tokens}) token(s)")

        response = self.qdrant.query_points(
            collection_name=self.collection,
            query=vector,
            score_threshold=self.score_min,
            limit=self.chunks_max,
            with_payload=True,
        )

        self.list_chunks(response.points)

    def query(self, question: str) -> None:
        """
        Get answer to question using RAG.
        :param question: Question.
        """
        logger.info(f"Querying:")
        print(Panel(f"[red]{question}"))

        logger.info(f" - Embedding question...")
        total_tokens, vector = self.openai.embed(question)
        logger.info(f"   - Used ({total_tokens}) token(s)")

        response = self.qdrant.query_points(
            collection_name=self.collection,
            query=vector,
            score_threshold=self.score_min,
            limit=self.chunks_max,
            with_payload=True,
        )

        self.list_chunks(response.points)

        context = []
        for point in response.points:
            context.append(
                "\n\n".join([
                    f"{point.payload['file_path']}:",
                    f"{point.payload['chunk']}",
                ])
            )
        context = "\n\n\n\n".join(context)

        answer = self.openai.query(question, context)

        logger.info(f" - Answer:")
        print(Panel(f"[green]{answer}"))

    @staticmethod
    def list_chunks(points: List[ScoredPoint]) -> None:
        """
        List chunks of retreived points.
        :param points: Retrieved points.
        """
        for point in points:
            match_percent = point.score * 100
            logger.info(f" - ({match_percent:.2f} %) matching chunk for file: '{point.payload['file_path']}':")
            answer = point.payload['chunk']
            print(Panel(f"[orange3]{answer}"))
