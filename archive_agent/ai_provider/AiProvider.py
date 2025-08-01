#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
import hashlib
from logging import Logger
from abc import ABC, abstractmethod
from typing import Callable, cast

from archive_agent.ai.AiResult import AiResult
from archive_agent.core.CacheManager import CacheManager

from archive_agent.ai_provider.AiProviderParams import AiProviderParams


class AiProvider(ABC):
    """
    AI provider.
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
        Initialize AI provider.
        :param logger: Logger.
        :param cache: Cache manager.
        :param invalidate_cache: Invalidate cache if enabled, probe cache otherwise.
        :param params: AI provider parameters.
        :param server_url: Server URL.
        """
        self.logger = logger

        self.cache = cache
        self.invalidate_cache = invalidate_cache

        self.params = params

        self.server_url = server_url

        self.supports_vision = self.params.model_vision != ""

    def _handle_cached_request(
            self,
            cache_key_prefix: str,
            callback: Callable,
            callback_kwargs: dict,
    ) -> AiResult:
        """
        Handle cached request.
        :param cache_key_prefix: Cache key prefix.
        :param callback: Callback to execute on a cache miss.
        :param callback_kwargs: Keyword arguments for the callback.
        :return: AI result.
        """
        callback_kwargs_str = json.dumps(callback_kwargs, sort_keys=True)
        params_str = self.params.get_static_cache_key()
        cache_str = f"{cache_key_prefix}:{callback_kwargs_str}:{params_str}"
        cache_key = hashlib.sha256(cache_str.encode('utf-8')).hexdigest()

        cached_result = self.cache.get(key=cache_key, display_key=cache_key_prefix)
        if cached_result is not None:
            ai_result: AiResult = cast(AiResult, cached_result)
            ai_result.total_tokens = 0  # Cached result consumed no tokens
            return ai_result

        result: AiResult = callback(**callback_kwargs)

        # Cache write.
        self.cache[cache_key] = result

        return result

    @abstractmethod
    def _perform_chunk_callback(self, prompt) -> AiResult:
        """
        Perform chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        raise NotImplementedError

    def chunk_callback(self, prompt: str) -> AiResult:
        """
        Chunk callback with caching.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        return self._handle_cached_request(
            cache_key_prefix="chunk_callback",
            callback=self._perform_chunk_callback,
            callback_kwargs=dict(prompt=prompt),
        )

    @abstractmethod
    def _perform_embed_callback(self, text: str) -> AiResult:
        """
        Perform embed callback.
        :param text: Text.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        raise NotImplementedError

    def embed_callback(self, text: str) -> AiResult:
        """
        Embed callback with caching.
        :param text: Text.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        return self._handle_cached_request(
            cache_key_prefix="embed_callback",
            callback=self._perform_embed_callback,
            callback_kwargs=dict(text=text),
        )

    @abstractmethod
    def _perform_rerank_callback(self, prompt: str) -> AiResult:
        """
        Perform rerank callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        raise NotImplementedError

    def rerank_callback(self, prompt: str) -> AiResult:
        """
        Rerank callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        return self._handle_cached_request(
            cache_key_prefix="rerank_callback",
            callback=self._perform_rerank_callback,
            callback_kwargs=dict(prompt=prompt),
        )

    @abstractmethod
    def _perform_query_callback(self, prompt: str) -> AiResult:
        """
        Perform query callback.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        raise NotImplementedError

    def query_callback(self, prompt: str) -> AiResult:
        """
        Query callback.
        NOTE: This call is NOT cached, as the user expects a novel answer on each call.
        :param prompt: Prompt.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        return self._perform_query_callback(prompt=prompt)

    @abstractmethod
    def _perform_vision_callback(self, prompt: str, image_base64: str) -> AiResult:
        """
        Perform vision callback.
        :param prompt: Prompt.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        raise NotImplementedError

    def vision_callback(self, prompt: str, image_base64: str) -> AiResult:
        """
        Vision callback with caching.
        :param prompt: Prompt.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: AI result.
        :raises AiProviderError: On error.
        """
        return self._handle_cached_request(
            cache_key_prefix="vision_callback",
            callback=self._perform_vision_callback,
            callback_kwargs=dict(prompt=prompt, image_base64=image_base64),
        )
