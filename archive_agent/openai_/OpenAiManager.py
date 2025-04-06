#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from pydantic import BaseModel
from openai import OpenAI, OpenAIError
from openai.types.responses.response import Response

from archive_agent.util.image import image_from_file, image_resize_safe, image_to_base64
from archive_agent.util import CliManager
from archive_agent.util import RetryManager

logger = logging.getLogger(__name__)


class QuerySchema(BaseModel):
    """
    QuerySchema.
    """
    answer: str
    reject: bool

    class Config:
        extra = "forbid"  # Ensures additionalProperties: false


class VisionSchema(BaseModel):
    """
    VisionSchema.
    """
    answer: str
    reject: bool

    class Config:
        extra = "forbid"  # Ensures additionalProperties: false


def response_to_QuerySchema(response: Response) -> QuerySchema:
    """
    Validate OpenAI response to QuerySchema.
    :param response: OpenAI response.
    :return: QuerySchema.
    """
    return QuerySchema.model_validate_json(response.output[0].content[0].text)


def response_to_VisionSchema(response: Response) -> VisionSchema:
    """
    Validate OpenAI response to VisionSchema.
    :param response: OpenAI response.
    :return: VisionSchema.
    """
    return VisionSchema.model_validate_json(response.output[0].content[0].text)


class OpenAiManager(RetryManager):
    """
    OpenAI manager.
    """

    @staticmethod
    def get_prompt_query(question: str, context: str):
        # TODO: Translate the `Strictly structure the answer like this:` into QuerySchema, then format it for use.
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

    def __init__(self, cli: CliManager, model_embed: str, model_query: str, model_vision: str, temp_query: float):
        """
        Initialize OpenAI manager.
        :param cli: CLI manager.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision.
        :param temp_query: Temperature of query model.
        """
        self.cli = cli
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision
        self.temp_query = temp_query

        self.client = OpenAI()

        self.total_tokens = 0

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
        if self.total_tokens > 0:
            logger.info(f"Used ({self.total_tokens}) OpenAI API token(s) in total")
        else:
            logger.info(f"No OpenAI API tokens used")

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
        self.total_tokens += response.usage.total_tokens
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
        self.total_tokens += response.usage.total_tokens

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        query_result = response_to_QuerySchema(response)

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
            self.total_tokens += response.usage.total_tokens

        if response.status == 'incomplete':
            raise OpenAIError("Vision response incomplete, probably due to token limits")

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        vision_result = response_to_VisionSchema(response)

        return vision_result
