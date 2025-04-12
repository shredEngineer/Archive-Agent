#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from abc import ABC, abstractmethod

from archive_agent.ai.AiResult import AiResult


class AiProvider(ABC):
    """
    AI provider.
    """

    def __init__(self):
        """
        Initialize AI provider.
        """
        pass

    @abstractmethod
    def chunk_callback(self, prompt) -> AiResult:
        """
        Chunk callback.
        :param prompt: Prompt.
        :return: AI result.
        """
        raise NotImplementedError

    @abstractmethod
    def embed_callback(self, text) -> AiResult:
        """
        Embed callback.
        :param text: Text.
        :return: AI result.
        """
        raise NotImplementedError

    @abstractmethod
    def query_callback(self, prompt: str) -> AiResult:
        """
        Query callback.
        :param prompt: Prompt.
        :return: AI result.
        """
        raise NotImplementedError

    @abstractmethod
    def vision_callback(self, prompt: str, image_base64: str) -> AiResult:
        """
        Vision callback.
        :param prompt: Prompt.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: AI result.
        """
        raise NotImplementedError
