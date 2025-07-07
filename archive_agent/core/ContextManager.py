#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from pathlib import Path
from typing import Optional

from archive_agent.profile.ProfileManager import ProfileManager
from archive_agent.config.ConfigManager import ConfigManager
from archive_agent.util.CliManager import CliManager
from archive_agent.config.DecoderSettings import DecoderSettings
from archive_agent.watchlist.WatchlistManager import WatchlistManager
from archive_agent.db.QdrantManager import QdrantManager
from archive_agent.core.CommitManager import CommitManager

from archive_agent.ai.AiManager import AiManager

from archive_agent.ai_provider.ai_provider_registry import ai_provider_registry
from archive_agent.ai_provider.AiProvider import AiProvider

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Context manager.
    """

    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize context manager.
        :param profile_name: Optional profile name to create or switch to (or "" to request prompt).
        """
        self.cli = CliManager()

        settings_path = Path.home() / ".archive-agent-settings"

        self.profile_manager = ProfileManager(
            cli=self.cli,
            settings_path=settings_path,
            profile_name=profile_name,
        )

        self.config = ConfigManager(
            cli=self.cli,
            settings_path=settings_path,
            profile_name=self.profile_manager.data[self.profile_manager.PROFILE_NAME],
        )

        self.watchlist = WatchlistManager(
            settings_path=settings_path,
            profile_name=self.profile_manager.data[self.profile_manager.PROFILE_NAME],
        )

        self.ai = AiManager(
            ai_provider=self._load_ai_provider(),
            cli=self.cli,
            chunk_lines_block=self.config.data[self.config.CHUNK_LINES_BLOCK],
        )

        self.decoder_settings = DecoderSettings(
            ocr_strategy=self.config.data[self.config.OCR_STRATEGY],
            ocr_auto_threshold=self.config.data[self.config.OCR_AUTO_THRESHOLD],
        )

        self.qdrant = QdrantManager(
            cli=self.cli,
            ai=self.ai,
            server_url=self.config.data[self.config.QDRANT_SERVER_URL],
            collection=self.config.data[self.config.QDRANT_COLLECTION],
            vector_size=self.config.data[self.config.AI_VECTOR_SIZE],
            score_min=self.config.data[self.config.QDRANT_SCORE_MIN],
            chunks_max=self.config.data[self.config.QDRANT_CHUNKS_MAX],
        )

        self.committer = CommitManager(self.watchlist, self.ai, self.decoder_settings, self.qdrant)

    def _load_ai_provider(self) -> AiProvider:
        """
        Load AI provider.
        :return: AI provider.
        """
        ai_provider_name = self.config.data[self.config.AI_PROVIDER]

        if ai_provider_name not in ai_provider_registry:
            raise ValueError(
                f"Invalid AI provider: '{ai_provider_name}' (must be one of {ai_provider_registry.keys()})"
            )

        ai_provider_class = ai_provider_registry[ai_provider_name]["class"]

        ai_provider = ai_provider_class(
            server_url=self.config.data[self.config.AI_SERVER_URL],
            model_chunk=self.config.data[self.config.AI_MODEL_CHUNK],
            model_embed=self.config.data[self.config.AI_MODEL_EMBED],
            model_query=self.config.data[self.config.AI_MODEL_QUERY],
            model_vision=self.config.data[self.config.AI_MODEL_VISION],
            temperature_query=self.config.data[self.config.AI_TEMPERATURE_QUERY],
        )

        ai_server_url = self.config.data[self.config.AI_SERVER_URL]
        logger.info(f"Using AI provider: '{ai_provider_name}' @ {ai_server_url}")
        return ai_provider
