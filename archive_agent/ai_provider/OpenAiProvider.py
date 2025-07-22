#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import os
from typing import Any, cast

from openai import OpenAI

from archive_agent.ai_provider.AiProvider import AiProvider
from archive_agent.ai_provider.AiProviderError import AiProviderError
from archive_agent.ai.AiResult import AiResult
from archive_agent.ai_provider.AiProviderParams import AiProviderParams

from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.ai.rerank.AiRerank import RerankSchema
from archive_agent.ai.query.AiQuery import QuerySchema
from archive_agent.ai.vision.AiVision import VisionSchema

from archive_agent.core.CacheManager import CacheManager

logger = logging.getLogger(__name__)


class OpenAiProvider(AiProvider):
    """
    OpenAI provider.
    """

    def __init__(
            self,
            cache: CacheManager,
            invalidate_cache: bool,
            params: AiProviderParams,
            server_url: str,
    ):
        """
        Initialize OpenAI provider.
        :param cache: Cache manager.
        :param invalidate_cache: Invalidate cache if enabled, probe cache otherwise.
        :param params: AI provider parameters.
        :param server_url: Server URL.
        """
        AiProvider.__init__(
            self,
            cache=cache,
            invalidate_cache=invalidate_cache,
            params=params,
        )

        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            logger.error(
                "Missing OPENAI_API_KEY.\n"
                "Please complete AI Provider Setup."
            )
            raise typer.Exit(code=1)

        self.client = OpenAI(base_url=server_url)

    def _perform_chunk_callback(self, prompt: str) -> AiResult:
        """
        Chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        # noinspection PyTypeChecker
        response = self.client.responses.create(
            model=self.params.model_chunk,
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
            raise AiProviderError(getattr(response, "refusal", None))

        # Pyright: We know this is always a text response in our use-case.
        content_item = response.output[0].content[0]  # type: ignore[reportAttributeAccessIssue]
        json_raw = getattr(content_item, "text", None)
        if json_raw is None:
            raise AiProviderError(f"Missing JSON: No text found in response content ({content_item!r})")
        try:
            parsed_schema = ChunkSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )

    def _perform_embed_callback(self, text: str) -> AiResult:
        """
        Embed callback.
        :param text: Text.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.embeddings.create(
            input=text,
            model=self.params.model_embed,
        )
        return AiResult(
            total_tokens=response.usage.total_tokens,
            embedding=response.data[0].embedding,
        )

    def _perform_rerank_callback(self, prompt: str) -> AiResult:
        """
        Rerank callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        # noinspection PyTypeChecker
        response = self.client.responses.create(
            model=self.params.model_rerank,
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
                    "name": RerankSchema.__name__,
                    "schema": RerankSchema.model_json_schema(),
                    "strict": True,
                },
            },
        )

        if getattr(response, "refusal", None):
            raise AiProviderError(getattr(response, "refusal", None))

        # Pyright: We know this is always a text response in our use-case.
        content_item = response.output[0].content[0]  # type: ignore[reportAttributeAccessIssue]
        json_raw = getattr(content_item, "text", None)
        if json_raw is None:
            raise AiProviderError(f"Missing JSON: No text found in response content ({content_item!r})")
        try:
            parsed_schema = RerankSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
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
        response = self.client.responses.create(
            model=self.params.model_query,
            temperature=self.params.temperature_query,
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
            raise AiProviderError(getattr(response, "refusal", None))

        # Pyright: We know this is always a text response in our use-case.
        content_item = response.output[0].content[0]  # type: ignore[reportAttributeAccessIssue]
        json_raw = getattr(content_item, "text", None)
        if json_raw is None:
            raise AiProviderError(f"Missing JSON: No text found in response content ({content_item!r})")
        try:
            parsed_schema = QuerySchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
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
        # noinspection PyTypeChecker
        response = self.client.responses.create(
            model=self.params.model_vision,
            input=cast(Any, [
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
            ]),
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
            raise AiProviderError("Vision response incomplete, probably due to token limits")

        if getattr(response, "refusal", None):
            raise AiProviderError(getattr(response, "refusal", None))

        # Pyright: We know this is always a text response in our use-case.
        content_item = response.output[0].content[0]  # type: ignore[reportAttributeAccessIssue]
        json_raw = getattr(content_item, "text", None)
        if json_raw is None:
            raise AiProviderError(f"Missing JSON: No text found in response content ({content_item!r})")
        try:
            parsed_schema = VisionSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )
