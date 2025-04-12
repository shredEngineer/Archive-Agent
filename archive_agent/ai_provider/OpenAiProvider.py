#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from openai import OpenAI, OpenAIError

from archive_agent.ai_provider.AiProvider import AiProvider
from archive_agent.ai.AiResult import AiResult

from archive_agent.ai_schema.ChunkSchema import ChunkSchema
from archive_agent.ai_schema.QuerySchema import QuerySchema
from archive_agent.ai_schema.VisionSchema import VisionSchema


class OpenAiProvider(AiProvider):
    """
    OpenAI provider.
    """

    def __init__(
            self,
            model_chunk: str,
            model_embed: str,
            model_query: str,
            model_vision: str,
            temp_query: float,
            chunk_lines_block: int,
    ):
        """
        Initialize OpenAI provider.
        :param model_chunk: Model for chunking.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision.
        :param temp_query: Temperature of query model.
        :param chunk_lines_block: Number of lines per block for chunking.
        """
        AiProvider.__init__(self)

        self.model_chunk = model_chunk
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision
        self.temp_query = temp_query

        self.chunk_lines_block = chunk_lines_block

        self.client = OpenAI()

    def chunk_callback(self, prompt: str) -> AiResult:
        """
        Chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        """
        response = self.client.responses.create(
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

        if getattr(response, "refusal", None):
            raise OpenAIError(getattr(response, "refusal", None))

        try:
            parsed_schema = ChunkSchema.model_validate_json(response.output[0].content[0].text)
        except Exception as e:
            raise OpenAIError(f"Invalid JSON: {e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,  # check makes pyright happy
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )

    def embed_callback(self, text: str) -> AiResult:
        """
        Embed callback.
        :param text: Text.
        :return: AI result.
        """
        response = self.client.embeddings.create(
            input=text,
            model=self.model_embed,
        )
        return AiResult(
            total_tokens=response.usage.total_tokens,
            embedding=response.data[0].embedding,
        )

    def query_callback(self, prompt: str) -> AiResult:
        """
        Query callback.
        :param prompt: Prompt.
        :return: AI result.
        """
        response = self.client.responses.create(
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

        if getattr(response, "refusal", None):
            raise OpenAIError(getattr(response, "refusal", None))

        try:
            parsed_schema = QuerySchema.model_validate_json(response.output[0].content[0].text)
        except Exception as e:
            raise OpenAIError(f"Invalid JSON: {e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,  # check makes pyright happy
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )

    def vision_callback(self, prompt: str, image_base64: str) -> AiResult:
        """
        Vision callback.
        :param prompt: Prompt.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: AI result.
        """
        response = self.client.responses.create(
            model=self.model_vision,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
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

        if response.status == 'incomplete':
            raise OpenAIError("Vision response incomplete, probably due to token limits")

        if getattr(response, "refusal", None):
            raise OpenAIError(getattr(response, "refusal", None))

        try:
            parsed_schema = VisionSchema.model_validate_json(response.output[0].content[0].text)
        except Exception as e:
            raise OpenAIError(f"Invalid JSON: {e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,  # check makes pyright happy
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )
