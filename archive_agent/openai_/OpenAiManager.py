#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from openai import OpenAI, OpenAIError

from archive_agent.schema.ChunkSchema import ChunkSchema
from archive_agent.schema.QuerySchema import QuerySchema
from archive_agent.schema.VisionSchema import VisionSchema
from archive_agent.util.text import prepend_line_numbers
from archive_agent.util import CliManager
from archive_agent.util import RetryManager

logger = logging.getLogger(__name__)


class OpenAiManager(RetryManager):
    """
    OpenAI manager.
    """

    @staticmethod
    def get_prompt_chunk(line_numbered_text: str):
        return "\n".join([
            f"Act as a semantinc chunking agent for RAG: Split the text into multiple chunks of related sentences.",
            f"Aim for paragraph-sized chunks, avoiding single-sentence chunks whenever possible.",
            f"Strictly adhere to the response schema:",
            f"- `chunk_start_lines`: List of chunk start lines, where the i-th element is the first line of chunk i.",
            f"  Since The first chunk always starts at line 1, the first element must be 1.",
            f"  Return at least 3 further elements that are unique and monotonically increasing.",
            f"\n\n",
            f"Text with line numbers:\n\"\"\"\n{line_numbered_text}\n\"\"\"\n\n",
        ])

    @staticmethod
    def get_prompt_query(question: str, context: str):
        return "\n".join([
            f"Act as a RAG agent: Use ONLY the context to answer the question.",
            f"Respect the context: Do NOT use your internal knowledge to answer.",
            f"Answer in great detail, considering ALL relevant aspects of the given context.",
            f"Do NOT include fillers like \"According to the provided context, ...\", \"Summarizing, ...\", etc.",
            f"Strictly adhere to the response schema:",
            f"- `question_rephrased`: Rephrased question, guessing the intent from the context.",
            f"- `answer_list`: List of all possible answers to the question, extensively considering the context.",
            f"- `answer_conclusion`: Summary and conclusion of the answers.",
            f"- `chunk_ref_list`: List of reference designators of chunks used in the answers.",
            f"  Enforce format as found in context: `<<< Chunk (X) / (Y) of file://... @ YYYY-MM-DD HH:MM:SS >>>`.",
            f"- `further_questions_list`: List of further questions following up on the question, context, and answer.",
            f"- `reject`: Rejection flag for rare cases where the context does not allow any answers at all.",
            f"  If rejecting, set `reject` to `true` and leave all other return values blank.",
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
            f"Strictly adhere to the response schema:",
            f"- `answer`: Multiple dense paragraphs containing the extracted information.",
            f"- `reject`: Rejection flag for rare cases where the image is entirely unreadable, corrupted, or blank.",
            f"  If rejecting, set `reject` to `true` and leave all other return values blank.",
        ])

    def __init__(
            self,
            cli: CliManager,
            model_chunk: str,
            model_embed: str,
            model_query: str,
            model_vision: str,
            temp_query: float,
            chunk_lines_block: int,
    ):
        """
        Initialize OpenAI manager.
        :param cli: CLI manager.
        :param model_chunk: Model for chunking.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision.
        :param temp_query: Temperature of query model.
        :param chunk_lines_block: Number of lines per block for chunking.
        """
        self.cli = cli
        self.model_chunk = model_chunk
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision
        self.temp_query = temp_query
        self.chunk_lines_block = chunk_lines_block

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
        if any([x > 0 for x in [
            self.total_tokens_chunk, self.total_tokens_embed, self.total_tokens_query, self.total_tokens_vision
        ]]):
            logger.info(
                f"Used OpenAI API token(s): "
                f"({self.total_tokens_chunk}) chunking, "
                f"({self.total_tokens_embed}) embedding, "
                f"({self.total_tokens_query}) query, "
                f"({self.total_tokens_vision}) vision"
            )
        else:
            logger.info(f"No OpenAI API tokens used")

    def chunk(self, sentences: List[str]) -> ChunkSchema:
        """
        Get chunks of sentences.
        :param sentences: Sentences.
        :return: ChunkSchema.
        """
        line_numbered_text = "\n".join(prepend_line_numbers(sentences))

        prompt = self.get_prompt_chunk(line_numbered_text)

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

        response = self.cli.format_openai_chunk(lambda: self.retry(callback), line_numbered_text)
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_chunk += response.usage.total_tokens

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        chunk_result = ChunkSchema.model_validate_json(response.output[0].content[0].text)

        if len(chunk_result.chunk_start_lines) == 0 or chunk_result.chunk_start_lines[0] != 1:
            raise RuntimeError(f"Invalid chunk start lines: {chunk_result.chunk_start_lines}")

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

    def vision(self, image_base64: str) -> VisionSchema:
        """
        Convert image to text.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: VisionSchema.
        """

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
