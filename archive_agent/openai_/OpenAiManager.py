#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from openai import OpenAI

from archive_agent.util.image import image_from_file, image_resize_safe, image_to_base64
from archive_agent.util import CliManager
from archive_agent.util import RetryManager

logger = logging.getLogger(__name__)


class OpenAiManager(RetryManager):
    """
    OpenAI manager.
    """

    @staticmethod
    def get_prompt_query(question: str, context: str):
        return "\n".join([
            f"Act as a RAG agent: Use ONLY the context to answer the question.",
            f"Respect the context: Do NOT use your internal knowledge to answer.",
            f"Answer in great detail, considering ALL relevant aspects of the given context.",
            f"Do NOT include fillers like \"According to the provided context, ...\".",
            f"Strictly structure the answer like this:",
            f"- Paragraph rephrasing the original question, guessing the intent from the context.",
            f"- List of all possible answers to the question, extensively considering the context.",
            f"- Paragraph summarizing and concluding the answer. Do NOT include fillers like \"Summarizing, ...\"",
            f"- List of all `file://` associated with snippets considered from the context, formatted markdown URLs."
            f"If the context does not allow any answers at all, ONLY output the token \"[NO FURTHER CONTEXT FOUND]\".",
            f"\n\n",
            f"Context:\n\"\"\"\n{context}\n\"\"\"\n\n",
            f"Question:\n\"\"\"\n{question}\n\"\"\"\n\n",
            f"Answer:",
        ])

    @staticmethod
    def get_prompt_vision():
        return "\n".join([
            f"Extract all text from the image: Transcribe verbatim, don't describe.",
            f"Only describe graphics or drawings in detail.",
            f"Output the answer as a single paragraph without newlines.",
        ])

    def __init__(self, cli: CliManager, model_embed: str, model_query: str, model_vision: str):
        """
        Initialize OpenAI manager.
        :param cli: CLI manager.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision.
        """
        self.cli = cli
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision

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
        logger.info(f"Used ({self.total_tokens}) token(s) in total")

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

    def query(self, question: str, context: str) -> str:
        """
        Get answer to question using RAG.
        :param question: Question.
        :param context: RAG context.
        :return: Answer.
        """
        prompt = self.get_prompt_query(question, context)

        def callback():
            return self.client.responses.create(
                model=self.model_query,
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
            )

        response = self.cli.format_openai_query(lambda: self.retry(callback), prompt)
        self.total_tokens += response.usage.total_tokens
        return response.output_text

    def vision(self, file_path: str) -> str:
        """
        Convert image to text.
        :param file_path: File path.
        :return: Image converted to text.
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
            )

        response = self.cli.format_openai_vision(lambda: self.retry(callback))
        self.total_tokens += response.usage.total_tokens
        return response.output_text
