#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
from logging import Logger

from ollama import Client as OllamaClient

from archive_agent.ai_provider.AiProvider import AiProvider
from archive_agent.ai_provider.AiProviderError import AiProviderError
from archive_agent.ai.AiResult import AiResult
from archive_agent.ai_provider.AiProviderParams import AiProviderParams

from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.ai.rerank.AiRerank import RerankSchema
from archive_agent.ai.query.AiQuery import QuerySchema
from archive_agent.ai.vision.AiVisionSchema import VisionSchema

from archive_agent.core.CacheManager import CacheManager


class OllamaProvider(AiProvider):
    """
    Ollama provider.
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
        Initialize Ollama provider.
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

        self.client = OllamaClient(host=self.server_url, timeout=AiProvider.AI_REQUEST_TIMEOUT_S)

    def _perform_chunk_callback(self, prompt: str) -> AiResult:
        """
        Chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.chat(
            model=self.params.model_chunk,
            messages=[
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": 0.0,
            },
            format=ChunkSchema.model_json_schema(),
        )

        formatted_response = json.dumps(response, indent=2, default=str)

        json_raw = response["message"]["content"]
        try:
            parsed_schema = ChunkSchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.get("eval_count", 0),
            output_text=response["message"]["content"],
            parsed_schema=parsed_schema,
        )

    def _perform_embed_callback(self, text: str) -> AiResult:
        """
        Embed callback.
        :param text: Text.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.embeddings(
            model=self.params.model_embed,
            prompt=text,
        )

        return AiResult(
            total_tokens=response.get("total_tokens", 0),
            embedding=response["embedding"],
        )

    def _perform_rerank_callback(self, prompt: str) -> AiResult:
        """
        Rerank callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.chat(
            model=self.params.model_rerank,
            messages=[
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": 0.0,
            },
            format=RerankSchema.model_json_schema(),
        )

        formatted_response = json.dumps(response, indent=2, default=str)

        json_raw = response["message"]["content"]
        try:
            parsed_schema = RerankSchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.get("eval_count", 0),
            output_text=response["message"]["content"],
            parsed_schema=parsed_schema,
        )

    def _perform_query_callback(self, prompt: str) -> AiResult:
        """
        Query callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.chat(
            model=self.params.model_query,
            messages=[
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": self.params.temperature_query,
            },
            format=QuerySchema.model_json_schema(),
        )

        formatted_response = json.dumps(response, indent=2, default=str)

        json_raw = response["message"]["content"]
        try:
            parsed_schema = QuerySchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.get("eval_count", 0),
            output_text=response["message"]["content"],
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
        response = self.client.chat(
            model=self.params.model_vision,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                },
            ],
            options={},
            format=VisionSchema.model_json_schema(),
        )

        formatted_response = json.dumps(response, indent=2, default=str)

        json_raw = response["message"]["content"]
        try:
            parsed_schema = VisionSchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.get("eval_count", 0),
            output_text=response["message"]["content"],
            parsed_schema=parsed_schema,
        )
