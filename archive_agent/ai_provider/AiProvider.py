#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import json
import hashlib
from abc import ABC, abstractmethod
from typing import Callable

from archive_agent.ai.AiResult import AiResult
from archive_agent.util.CacheManager import CacheManager

from archive_agent.ai_provider.AiProviderParams import AiProviderParams

logger = logging.getLogger(__name__)


class AiProvider(ABC):
    """
    AI provider.
    """

    def __init__(
            self,
            cache: CacheManager,
            invalidate_cache: bool,
            params: AiProviderParams,
    ):
        """
        Initialize AI provider.
        :param cache: Cache manager.
        :param invalidate_cache: Invalidate cache if enabled, probe cache otherwise.
        :param params: AI provider parameters.
        """
        self.cache = cache
        self.invalidate_cache = invalidate_cache

        self.params = params
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

        if self.invalidate_cache:
            logger.info(f"Cache bypass (--invalidate_cache) for '{cache_key_prefix}'")
        elif cache_key in self.cache:
            logger.info(f"Cache hit for '{cache_key_prefix}'")
            return self.cache[cache_key]
        else:
            logger.info(f"Cache miss for '{cache_key_prefix}'")

        result = callback(**callback_kwargs)
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
