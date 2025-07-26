#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import Type

from archive_agent.ai.AiManager import AiManager

from archive_agent.ai_provider.AiProvider import AiProvider, AiProviderParams

from archive_agent.core.CliManager import CliManager

from archive_agent.core.CacheManager import CacheManager


class AiManagerFactory(Exception):

    def __init__(
            self,
            cli: CliManager,
            chunk_lines_block: int,
            chunk_words_target: int,
            ai_provider_class: Type[AiProvider],
            ai_provider_params: AiProviderParams,
            ai_cache: CacheManager,
            invalidate_cache: bool,
            server_url: str,
    ):
        """
        Initialize AI manager factory.
        :param cli: CLI manager.
        :param chunk_lines_block: Number of lines per block for chunking.
        :param chunk_words_target: Target number of words per chunk.
        :param ai_provider_class: AI provider class.
        :param ai_cache: AI cache.
        :param invalidate_cache: Invalidate cache if enabled, probe cache otherwise.
        :param server_url: Server URL.
        """
        self.cli = cli
        self.chunk_lines_block = chunk_lines_block
        self.chunk_words_target = chunk_words_target
        self.ai_provider_class = ai_provider_class
        self.ai_provider_params = ai_provider_params
        self.ai_cache = ai_cache
        self.invalidate_cache = invalidate_cache
        self.server_url = server_url

    def get_ai(self) -> AiManager:
        """
        Get new AI manager instance.
        """
        return AiManager(
            cli=self.cli,
            chunk_lines_block=self.chunk_lines_block,
            chunk_words_target=self.chunk_words_target,
            ai_provider=self._load_ai_provider(),
        )

    def _load_ai_provider(self) -> AiProvider:
        """
        Load AI provider.
        :return: AI provider.
        """
        ai_provider = self.ai_provider_class(
            logger=self.cli.logger,
            cache=self.ai_cache,
            invalidate_cache=self.invalidate_cache,
            params=self.ai_provider_params,
            server_url=self.server_url,
        )

        return ai_provider
