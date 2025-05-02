#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from openai import OpenAI

from archive_agent.ai_provider.AiProvider import AiProvider
from archive_agent.ai_provider.AiProviderError import AiProviderError
from archive_agent.ai.AiResult import AiResult

from archive_agent.ai_schema.ChunkSchema import ChunkSchema
from archive_agent.ai_schema.QuerySchema import QuerySchema
from archive_agent.ai_schema.VisionSchema import VisionSchema


class LMStudioProvider(AiProvider):
    """
    LM Studio provider with structured output and optional vision support.
    """

    def __init__(
        self,
        server_url: str,
        model_chunk: str,
        model_embed: str,
        model_query: str,
        model_vision: str,
        temperature_query: float,
    ):
        """
        Initialize LM Studio provider.
        :param server_url: Server URL.
        :param model_chunk: Model for chunking.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision (leave empty to disable vision support).
        :param temperature_query: Temperature of query model.
        """
        AiProvider.__init__(self, supports_vision=model_vision != "")

        self.model_chunk = model_chunk
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision
        self.temperature_query = temperature_query

        self.client = OpenAI(base_url=server_url, api_key="lm-studio")

    def chunk_callback(self, prompt: str) -> AiResult:
        """
        Chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        # noinspection PyTypeChecker
        response = self.client.chat.completions.create(
            model=self.model_chunk,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": ChunkSchema.__name__,
                    "schema": ChunkSchema.model_json_schema(),
                    "strict": True,
                },
            },
        )

        json_raw = response.choices[0].message.content
        try:
            parsed_schema = ChunkSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=json_raw,
            parsed_schema=parsed_schema,
        )

    def embed_callback(self, text: str) -> AiResult:
        """
        Embed callback.
        :param text: Text.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model_embed
            )

            return AiResult(
                total_tokens=response.usage.total_tokens,
                embedding=response.data[0].embedding
            )

        except Exception as e:
            raise AiProviderError(f"Embedding failed:\n{e}")

    def query_callback(self, prompt: str) -> AiResult:
        """
        Query callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        # noinspection PyTypeChecker
        response = self.client.chat.completions.create(
            model=self.model_query,
            temperature=self.temperature_query,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": QuerySchema.__name__,
                    "schema": QuerySchema.model_json_schema(),
                    "strict": True,
                },
            },
        )

        json_raw = response.choices[0].message.content
        try:
            parsed_schema = QuerySchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=json_raw,
            parsed_schema=parsed_schema,
        )

    def vision_callback(self, prompt: str, image_base64: str) -> AiResult:
        """
        Vision callback.
        :param prompt: Prompt.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        if not self.model_vision:
            raise AiProviderError("Vision model is not configured.")

        # noinspection PyTypeChecker
        response = self.client.chat.completions.create(
            model=self.model_vision,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": VisionSchema.__name__,
                    "schema": VisionSchema.model_json_schema(),
                    "strict": True,
                },
            },
        )

        json_raw = response.choices[0].message.content
        try:
            parsed_schema = VisionSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=json_raw,
            parsed_schema=parsed_schema,
        )
