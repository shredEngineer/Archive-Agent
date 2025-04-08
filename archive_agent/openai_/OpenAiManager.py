#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from pydantic import BaseModel
from openai import OpenAI, OpenAIError

from archive_agent.util.image import image_from_file, image_resize_safe, image_to_base64
from archive_agent.util import CliManager
from archive_agent.util import RetryManager

logger = logging.getLogger(__name__)


class ChunkSchema(BaseModel):

    class Chunk(BaseModel):
        text: str

        class Config:
            extra = "forbid"  # Ensures additionalProperties: false

    chunks: List[Chunk]

    class Config:
        extra = "forbid"  # Ensures additionalProperties: false


class QuerySchema(BaseModel):
    answer: str
    reject: bool

    class Config:
        extra = "forbid"  # Ensures additionalProperties: false


class VisionSchema(BaseModel):
    answer: str
    reject: bool

    class Config:
        extra = "forbid"  # Ensures additionalProperties: false


class OpenAiManager(RetryManager):
    """
    OpenAI manager.
    """

    @staticmethod
    def get_prompt_chunk(text: str):
        return "\n".join([
            f"Act as a semantic chunking agent for RAG: Split the text into multiple semantically distinct chunks.",
            f"Each chunk must start and end at a sentence or formatting boundary."
            f"The chunks must be a complete, sequential, and exclusive partition of the original text.",
            f"Process ALL text: If the chunks were concatenated together, they MUST return the original text."
            f"Each chunk should contain as many sentences as necessary for the particular semantic group.",
            f"Semantic groups should span a specific topic, narrative, or logical section.",
            f"Avoid single-sentence chunks, as sentences USUALLY occur within a greater semantic structure.",
            f"Capture that greater semantic structure and produce chunks of reasonable size."
            f"Return the chunks in `chunks`.",
            f"\n\n",
            f"Context:\n\"\"\"\n{text}\n\"\"\"\n\n",
        ])

    @staticmethod
    def get_prompt_query(question: str, context: str):
        """
            TODO: Translate the `Strictly structure the answer like this:` into QuerySchema, then format it for use.
            - Rephrased question
            - List of Answers
            - Conclusion
            - Relevant URI list
            - Follow-up questions
        """
        return "\n".join([
            f"Act as a RAG agent: Use ONLY the context to answer the question.",
            f"Respect the context: Do NOT use your internal knowledge to answer.",
            f"Answer in great detail, considering ALL relevant aspects of the given context.",
            f"Do NOT include fillers like \"According to the provided context, ...\".",
            f"Strictly structure the answer like this:",
            f"- Paragraph rephrasing the original question, guessing the intent from the context.",
            f"- List of all possible answers to the question, extensively considering the context.",
            f"- Paragraph summarizing and concluding the answer. Do NOT include fillers like \"Summarizing, ...\"",
            f"- List of all `file://` associated with snippets considered from the context, formatted markdown URLs.",
            f"In extremely rase cases, reject questions if the context does not allow any answers at all.",
            f"If rejecting, set `reject` to `true` and `answer` to a very short description for rejecting.",
            f"\n\n",
            f"Context:\n\"\"\"\n{context}\n\"\"\"\n\n",
            f"Question:\n\"\"\"\n{question}\n\"\"\"\n\n",
            f"Answer:",
        ])

    @staticmethod
    def get_prompt_vision():
        return "\n".join([
            f"Act as a vision agent for RAG: Extract all visible text verbatim and with maximum accuracy.",
            f"Analyze images of notes, whiteboards, diagrams, documents, screenshots, and photos of scenes or objects."
            f"For screenshots, focus on the window or video frame in the foreground.",
            f"Describe ONLY meaningful relationships between relevant visible elements.",
            f"Prioritize written content, ignoring minor details like grid lines or binder holes."
            f"As `answer` return multiple dense paragraphs containing the extracted information.",
            f"In extremely rase cases, reject entirely unreadable, corrupted, or blank images.",
            f"If rejecting, set `reject` to `true` and `answer` to the reason for rejecting the image.",
        ])

    def __init__(
            self,
            cli: CliManager,
            model_chunk: str,
            model_embed: str,
            model_query: str,
            model_vision: str,
            temp_query: float,
    ):
        """
        Initialize OpenAI manager.
        :param cli: CLI manager.
        :param model_chunk: Model for chunking.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision.
        :param temp_query: Temperature of query model.
        """
        self.cli = cli
        self.model_chunk = model_chunk
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision
        self.temp_query = temp_query

        self.client = OpenAI()

        self.total_tokens_chunk = 0
        self.total_tokens_embed = 0
        self.total_tokens_query = 0
        self.total_tokens_vision = 0

        RetryManager.__init__(
            self,
            predelay=0,
            delay_min=0,
            delay_max=60,
            backoff_exponent=2,
            retries=10,
        )

    def usage(self) -> None:
        """
        Show usage.
        """
        if (
                self.total_tokens_chunk > 0 or
                self.total_tokens_embed > 0 or
                self.total_tokens_query > 0 or
                self.total_tokens_vision > 0
        ):
            logger.info(
                f"Used OpenAI API token(s): "
                f"({self.total_tokens_chunk}) chunking, "
                f"({self.total_tokens_embed}) embedding, "
                f"({self.total_tokens_query}) query, "
                f"({self.total_tokens_vision}) vision"
            )
        else:
            logger.info(f"No OpenAI API tokens used")

    def chunk(self, text: str) -> ChunkSchema:
        """
        Get chunks of text.
        :param text: Text.
        :return: ChunkSchema.
        """
        prompt = self.get_prompt_chunk(text)

        def callback():
            return self.client.responses.create(
                model=self.model_chunk,
                temperature=0,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            },
                        ],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": ChunkSchema.__name__,
                        "schema": ChunkSchema.model_json_schema(),
                        "strict": True,
                    },
                },
            )

        response = self.cli.format_openai_chunk(lambda: self.retry(callback), text)
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_chunk += response.usage.total_tokens

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        chunk_result = ChunkSchema.model_validate_json(response.output[0].content[0].text)

        return chunk_result

    def embed(self, text: str) -> List[float]:
        """
        Embed text.
        :param text: Text.
        :return: Embedding vector.
        """
        def callback():
            return self.client.embeddings.create(
                input=text,
                model=self.model_embed,
            )

        response = self.cli.format_openai_embed(lambda: self.retry(callback), text)
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_embed += response.usage.total_tokens
        return response.data[0].embedding

    def query(self, question: str, context: str) -> QuerySchema:
        """
        Get answer to question using RAG.
        :param question: Question.
        :param context: RAG context.
        :return: QuerySchema.
        """
        prompt = self.get_prompt_query(question, context)

        def callback():
            return self.client.responses.create(
                model=self.model_query,
                temperature=self.temp_query,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            },
                        ],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": QuerySchema.__name__,
                        "schema": QuerySchema.model_json_schema(),
                        "strict": True,
                    },
                },
            )

        response = self.cli.format_openai_query(lambda: self.retry(callback), prompt)
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_query += response.usage.total_tokens

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        query_result = QuerySchema.model_validate_json(response.output[0].content[0].text)

        return query_result

    def vision(self, file_path: str) -> VisionSchema:
        """
        Convert image to text.
        :param file_path: File path.
        :return: VisionSchema.
        """
        image_base64 = image_to_base64(image_resize_safe(image_from_file(file_path)))

        def callback():
            return self.client.responses.create(
                model=self.model_vision,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": self.get_prompt_vision()
                            },
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{image_base64}",
                            },
                        ],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": VisionSchema.__name__,
                        "schema": VisionSchema.model_json_schema(),
                        "strict": True,
                    },
                },
            )

        response = self.cli.format_openai_vision(lambda: self.retry(callback))
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_vision += response.usage.total_tokens

        if response.status == 'incomplete':
            raise OpenAIError("Vision response incomplete, probably due to token limits")

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        vision_result = VisionSchema.model_validate_json(response.output[0].content[0].text)

        return vision_result
