#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from rich import print
from rich.panel import Panel

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, Filter, FilterSelector, FieldCondition, MatchValue

from archive_agent.openai_ import OpenAiManager
from archive_agent.data import FileData

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)


class QdrantManager:
    """
    Qdrant manager.
    """

    SEARCH_LIMIT = 5
    QUERY_LIMIT = 5

    def __init__(self, openai: OpenAiManager, server_url: str, collection: str, vector_size: int):
        """
        Initialize Qdrant manager.
        :param openai: OpenAI manager.
        :param server_url: Server URL.
        :param collection: Collection name.
        :param vector_size: Vector size.
        """
        self.openai = openai
        self.qdrant = QdrantClient(url=server_url)

        self.collection = collection
        self.vector_size = vector_size

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

        data = FileData(openai=self.openai, file_path=file_path, file_mtime=file_mtime)
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
            limit=self.QUERY_LIMIT,
            with_payload=True,
        )

        for point in response.points:
            logger.info(f" - Matching chunk for file: '{point.payload['file_path']}':")
            answer = point.payload['chunk']
            print(Panel(f"[green]{answer}"))

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
            limit=self.QUERY_LIMIT,
            with_payload=True,
        )

        context = []

        for point in response.points:
            context.append(
                "\n\n".join([
                    f"{point.payload['file_path']}:",
                    f"{point.payload['chunk']}",
                ])
            )

        for point in response.points:
            match_percent = point.score * 100
            logger.info(f" - ({match_percent:.2f} %) matching chunk in file: '{point.payload['file_path']}':")
            answer = point.payload['chunk']
            print(Panel(f"[orange3]{answer}"))

        context = "\n\n\n\n".join(context)

        answer = self.openai.query(question, context)

        logger.info(f" - Answer:")
        print(Panel(f"[green]{answer}"))
