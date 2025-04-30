#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from ollama import Client as OllamaClient

from archive_agent.ai_provider.AiProvider import AiProvider
from archive_agent.ai_provider.AiProviderError import AiProviderError
from archive_agent.ai.AiResult import AiResult

from archive_agent.ai_schema.ChunkSchema import ChunkSchema
from archive_agent.ai_schema.QuerySchema import QuerySchema
from archive_agent.ai_schema.VisionSchema import VisionSchema


class OllamaProvider(AiProvider):
    """
    Ollama provider.
    """

    def __init__(
            self,
            model_chunk: str,
            model_embed: str,
            model_query: str,
            model_vision: str,
            temperature_query: float,
    ):
        """
        Initialize Ollama provider.
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

        self.client = OllamaClient(host='http://localhost:11434')

    def chunk_callback(self, prompt: str) -> AiResult:
        """
        Chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.chat(
            model=self.model_chunk,
            messages=[
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": 0.0,
            },
            format=ChunkSchema.model_json_schema(),
        )

        json_raw = response["message"]["content"]
        try:
            parsed_schema = ChunkSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.get("eval_count", 0),
            output_text=response["message"]["content"],
            parsed_schema=parsed_schema,
        )

    def embed_callback(self, text: str) -> AiResult:
        """
        Embed callback.
        :param text: Text.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.embeddings(
            model=self.model_embed,
            prompt=text,
        )

        return AiResult(
            total_tokens=response.get("total_tokens", 0),
            embedding=response["embedding"],
        )

    def query_callback(self, prompt: str) -> AiResult:
        """
        Query callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        response = self.client.chat(
            model=self.model_query,
            messages=[
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": self.temperature_query,
            },
            format=QuerySchema.model_json_schema(),
        )

        json_raw = response["message"]["content"]
        try:
            parsed_schema = QuerySchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.get("eval_count", 0),
            output_text=response["message"]["content"],
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
        response = self.client.chat(
            model=self.model_vision,
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

        json_raw = response["message"]["content"]
        try:
            parsed_schema = VisionSchema.model_validate_json(json_raw)
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}")

        return AiResult(
            total_tokens=response.get("eval_count", 0),
            output_text=response["message"]["content"],
            parsed_schema=parsed_schema,
        )
