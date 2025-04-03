#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from rich import print
from rich.panel import Panel
from typing import List

from openai import OpenAI

from archive_agent.util.image import image_from_file, image_resize_safe, image_to_base64

logger = logging.getLogger(__name__)


class OpenAiManager:
    """
    OpenAI manager.
    """

    PROMPT_VISION = "What's in this image? Extract and output every detail."

    def __init__(self, model_embed: str, model_query: str, model_vision: str):
        """
        Initialize OpenAI manager.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision.
        """
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision

        self.client = OpenAI()

    def embed(self, text: str) -> (int, List[float]):
        """
        Embed text.
        :param text: Text.
        :return: (Total tokens, Embedding vector).
        """
        response = self.client.embeddings.create(
            input=text,
            model=self.model_embed,
        )

        return response.usage.total_tokens, response.data[0].embedding

    def query(self, question: str, context: str) -> str:
        """
        Get answer to question using RAG.
        :param question: Question.
        :param context: RAG context.
        :return: Answer.
        """
        prompt = (
            f"Use the following context to accurately answer the question."
            f"If the context does not contain sufficient information, indicate that clearly instead of guessing."
            f""
            f"Context:"
            f"\"\"\""
            f"{context}"
            f"\"\"\""
            f""
            f"Question:"
            f"\"\"\""
            f"{question}"
            f"\"\"\""
            f""
            f"Answer:"
        )

        response = self.client.responses.create(
            model=self.model_query,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                    ],
                },
            ],
        )

        logger.info(f"   - Used ({response.usage.total_tokens}) token(s)")

        return response.output_text

    def vision(self, file_path: str) -> str:
        """
        Convert image to text.
        :param file_path: File path.
        :return: Image converted to text.
        """
        logger.info(f" - Image vision...")

        image_base64 = image_to_base64(image_resize_safe(image_from_file(file_path)))

        response = self.client.responses.create(
            model=self.model_vision,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self.PROMPT_VISION
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{image_base64}",
                        },
                    ],
                },
            ],
        )

        print(Panel(f"[orange3]{response.output_text}"))

        logger.info(f"   - Used ({response.usage.total_tokens}) token(s)")

        return response.output_text
