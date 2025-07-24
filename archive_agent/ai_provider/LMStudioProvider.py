#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
from logging import Logger

from openai import OpenAI

from archive_agent.ai_provider.AiProvider import AiProvider
from archive_agent.ai_provider.AiProviderError import AiProviderError
from archive_agent.ai.AiResult import AiResult
from archive_agent.ai_provider.AiProviderParams import AiProviderParams

from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.ai.rerank.AiRerank import RerankSchema
from archive_agent.ai.query.AiQuery import QuerySchema
from archive_agent.ai.vision.AiVisionSchema import VisionSchema

from archive_agent.core.CacheManager import CacheManager


class LMStudioProvider(AiProvider):
    """
    LM Studio provider with structured output and optional vision support.
    """

    def __init__(
            self,
            logger: Logger,
            cache: CacheManager,
            invalidate_cache: bool,
            params: AiProviderParams,
            server_url: str,
    ):
        """
        Initialize LM Studio provider.
        :param logger: Logger.
        :param cache: Cache manager.
        :param invalidate_cache: Invalidate cache if enabled, probe cache otherwise.
        :param params: AI provider parameters.
        :param server_url: Server URL.
        """
        AiProvider.__init__(
            self,
            logger=logger,
            cache=cache,
            invalidate_cache=invalidate_cache,
            params=params,
            server_url=server_url,
        )

        self.client = OpenAI(base_url=self.server_url, api_key="lm-studio")

    def _perform_chunk_callback(self, prompt: str) -> AiResult:
        """
        Chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        # noinspection PyTypeChecker
        response = self.client.chat.completions.create(
            model=self.params.model_chunk,
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

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        json_raw = response.choices[0].message.content
        if json_raw is None:
            raise AiProviderError(f"Missing JSON\n{formatted_response}")
        try:
            parsed_schema = ChunkSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=json_raw,
            parsed_schema=parsed_schema,
        )

    def _perform_embed_callback(self, text: str) -> AiResult:
        """
        Embed callback.
        :param text: Text.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.params.model_embed
            )

            return AiResult(
                total_tokens=response.usage.total_tokens,
                embedding=response.data[0].embedding
            )

        except Exception as e:
            raise AiProviderError(f"Embedding failed:\n{e}")

    def _perform_rerank_callback(self, prompt: str) -> AiResult:
        """
        Rerank callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        # noinspection PyTypeChecker
        response = self.client.chat.completions.create(
            model=self.params.model_rerank,
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
                    "name": RerankSchema.__name__,
                    "schema": RerankSchema.model_json_schema(),
                    "strict": True,
                },
            },
        )

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        json_raw = response.choices[0].message.content
        if json_raw is None:
            raise AiProviderError(f"Missing JSON\n{formatted_response}")
        try:
            parsed_schema = RerankSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=json_raw,
            parsed_schema=parsed_schema,
        )

    def _perform_query_callback(self, prompt: str) -> AiResult:
        """
        Query callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        # noinspection PyTypeChecker
        response = self.client.chat.completions.create(
            model=self.params.model_query,
            temperature=self.params.temperature_query,
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

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        json_raw = response.choices[0].message.content
        if json_raw is None:
            raise AiProviderError(f"Missing JSON\n{formatted_response}")
        try:
            parsed_schema = QuerySchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=json_raw,
            parsed_schema=parsed_schema,
        )

    def _perform_vision_callback(self, prompt: str, image_base64: str) -> AiResult:
        """
        Vision callback.
        :param prompt: Prompt.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        if not self.params.model_vision:
            raise AiProviderError("Vision model is not configured.")

        # noinspection PyTypeChecker
        response = self.client.chat.completions.create(
            model=self.params.model_vision,
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

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        json_raw = response.choices[0].message.content
        if json_raw is None:
            raise AiProviderError(f"Missing JSON\n{formatted_response}")
        try:
            parsed_schema = VisionSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=json_raw,
            parsed_schema=parsed_schema,
        )
