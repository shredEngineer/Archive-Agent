#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import os
import json
import traceback
from logging import Logger
from typing import Any, cast

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


# ----------------------------------------------------------------------
# GPT-5 defaults (per operation)
# ----------------------------------------------------------------------
GPT_5_REASONING_CHUNK = {"effort": "minimal"}
GPT_5_VERBOSITY_CHUNK = "low"

GPT_5_REASONING_QUERY = {"effort": "low"}  # WARNING: "high" effort takes  F O R E V E R
GPT_5_VERBOSITY_QUERY = "high"

GPT_5_REASONING_VISION = {"effort": "minimal"}
GPT_5_VERBOSITY_VISION = "low"

GPT_5_REASONING_RERANK = {"effort": "minimal"}
GPT_5_VERBOSITY_RERANK = "low"


def _extract_text_from_response(response: Any) -> str:
    """
    Extract the JSON text payload from an OpenAI response.
    Works across GPT-4.1 and GPT-5 response formats.
    """
    # noinspection PyBroadException
    try:
        # Case 1: GPT-4.1 style (output[0].content[0].text)
        if hasattr(response.output[0], "content"):
            content_item = response.output[0].content[0]
            if hasattr(content_item, "text") and content_item.text:
                return content_item.text
    except Exception:
        pass

    # Case 2: GPT-5 style (no .content, use .output_text)
    if getattr(response, "output_text", None):
        return response.output_text

    formatted_response = json.dumps(response.__dict__, indent=2, default=str)
    raise AiProviderError(f"Missing JSON: Could not extract text from response\n{formatted_response}")


class OpenAiProvider(AiProvider):
    """
    OpenAI provider.
    """

    def __init__(
            self,
            logger: Logger,
            cache: CacheManager,
            invalidate_cache: bool,
            params: AiProviderParams,
            server_url: str,
    ):
        AiProvider.__init__(
            self,
            logger=logger,
            cache=cache,
            invalidate_cache=invalidate_cache,
            params=params,
            server_url=server_url,
        )

        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            self.logger.error(
                "Missing OPENAI_API_KEY.\n"
                "Please complete AI Provider Setup."
            )
            raise typer.Exit(code=1)

        self.client = OpenAI(base_url=self.server_url, timeout=AiProvider.AI_REQUEST_TIMEOUT_S)

    def _responses_create(self, model: str, op: str, **kwargs: Any) -> Any:
        """
        Wrapper around client.responses.create that omits unsupported params
        for GPT-5 and applies hardcoded defaults for reasoning/verbosity.
        """
        if model.startswith("gpt-5"):
            # Drop unsupported fields
            kwargs.pop("temperature", None)
            kwargs.pop("top_p", None)
            kwargs.pop("logprobs", None)

            # Apply per-operation defaults
            if op == "chunk":
                kwargs.setdefault("reasoning", GPT_5_REASONING_CHUNK)
                if "text" in kwargs and isinstance(kwargs["text"], dict):
                    kwargs["text"].setdefault("verbosity", GPT_5_VERBOSITY_CHUNK)
            elif op == "query":
                kwargs.setdefault("reasoning", GPT_5_REASONING_QUERY)
                if "text" in kwargs and isinstance(kwargs["text"], dict):
                    kwargs["text"].setdefault("verbosity", GPT_5_VERBOSITY_QUERY)
            elif op == "vision":
                kwargs.setdefault("reasoning", GPT_5_REASONING_VISION)
                if "text" in kwargs and isinstance(kwargs["text"], dict):
                    kwargs["text"].setdefault("verbosity", GPT_5_VERBOSITY_VISION)
            elif op == "rerank":
                kwargs.setdefault("reasoning", GPT_5_REASONING_RERANK)
                if "text" in kwargs and isinstance(kwargs["text"], dict):
                    kwargs["text"].setdefault("verbosity", GPT_5_VERBOSITY_RERANK)

        return self.client.responses.create(model=model, **kwargs)

    def _perform_chunk_callback(self, prompt: str) -> AiResult:
        # noinspection PyTypeChecker
        response = self._responses_create(
            model=self.params.model_chunk,
            op="chunk",
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

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        if getattr(response, 'refusal', None):
            raise AiProviderError(f"Chunk refusal\n{formatted_response}")

        json_raw = _extract_text_from_response(response)
        try:
            parsed_schema = ChunkSchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )

    def _perform_embed_callback(self, text: str) -> AiResult:
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.params.model_embed,
            )
            return AiResult(
                total_tokens=response.usage.total_tokens,
                embedding=response.data[0].embedding,
            )
        except Exception as e:
            text_preview = text[:200] + "..." if len(text) > 200 else text
            tb = traceback.format_exc()
            raise AiProviderError(
                f"Embedding failed ({len(text)} chars): {type(e).__name__}: {e}\n"
                f"Text: {text_preview}\n"
                f"Traceback:\n{tb}"
            )

    def _perform_rerank_callback(self, prompt: str) -> AiResult:
        # noinspection PyTypeChecker
        response = self._responses_create(
            model=self.params.model_rerank,
            op="rerank",
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

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        if getattr(response, 'refusal', None):
            raise AiProviderError(f"Rerank refusal\n{formatted_response}")

        json_raw = _extract_text_from_response(response)
        try:
            parsed_schema = RerankSchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )

    def _perform_query_callback(self, prompt: str) -> AiResult:
        # noinspection PyTypeChecker
        response = self._responses_create(
            model=self.params.model_query,
            op="query",
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

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        if getattr(response, 'refusal', None):
            raise AiProviderError(f"Query refusal\n{formatted_response}")

        json_raw = _extract_text_from_response(response)
        try:
            parsed_schema = QuerySchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )

    def _perform_vision_callback(self, prompt: str, image_base64: str) -> AiResult:
        # noinspection PyTypeChecker
        response = self._responses_create(
            model=self.params.model_vision,
            op="vision",
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

        formatted_response = json.dumps(response.__dict__, indent=2, default=str)

        if response.status == 'incomplete':
            openai_incomplete_details = getattr(response, 'incomplete_details', None)
            if openai_incomplete_details is not None:
                openai_incomplete_details_reason = getattr(openai_incomplete_details, 'reason', None)
                if openai_incomplete_details_reason == 'content_filter':
                    self.logger.critical(f"⚠️ Vision content filter triggered by OpenAI\n{formatted_response}")
                    return AiResult(
                        total_tokens=response.usage.total_tokens if response.usage else 0,
                        output_text="",
                        parsed_schema=VisionSchema(
                            is_rejected=True,
                            rejection_reason="Vision content filter triggered by OpenAI",
                            entities=[],
                            relations=[],
                            answer=""
                        )
                    )
            raise AiProviderError(f"Vision response incomplete for unknown/unhandled reason\n{formatted_response}")

        openai_refusal = getattr(response, 'refusal', None)
        if openai_refusal is not None:
            self.logger.critical(f"⚠️ Vision refusal triggered by OpenAI\n{formatted_response}")
            return AiResult(
                total_tokens=response.usage.total_tokens if response.usage else 0,
                output_text="",
                parsed_schema=VisionSchema(
                    is_rejected=True,
                    rejection_reason=f"Refusal by OpenAI: {openai_refusal}",
                    entities=[],
                    relations=[],
                    answer=""
                )
            )

        json_raw = _extract_text_from_response(response)
        try:
            parsed_schema = VisionSchema.model_validate_json(self._sanitize_json(json_raw))
        except Exception as e:
            raise AiProviderError(f"Invalid JSON:\n{json_raw}\n{e}\n{formatted_response}")

        return AiResult(
            total_tokens=response.usage.total_tokens if response.usage else 0,
            output_text=response.output_text,
            parsed_schema=parsed_schema,
        )
