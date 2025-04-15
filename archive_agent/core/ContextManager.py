#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from pathlib import Path

from archive_agent.util.CliManager import CliManager
from archive_agent.config.ConfigManager import ConfigManager
from archive_agent.watchlist.WatchlistManager import WatchlistManager
from archive_agent.ai.AiManager import AiManager
from archive_agent.db.QdrantManager import QdrantManager
from archive_agent.core.CommitManager import CommitManager


class ContextManager:
    """
    Context manager.
    """

    def __init__(self):
        """
        Initialize context manager.
        """
        settings_path = Path.home() / ".archive-agent-settings"
        profile_path = settings_path / "default"

        self.cli = CliManager()

        self.config = ConfigManager(profile_path)

        self.watchlist = WatchlistManager(profile_path)

        self.ai = AiManager(
            cli=self.cli,
            model_chunk=self.config.data[self.config.OPENAI_MODEL_CHUNK],
            model_embed=self.config.data[self.config.OPENAI_MODEL_EMBED],
            model_query=self.config.data[self.config.OPENAI_MODEL_QUERY],
            model_vision=self.config.data[self.config.OPENAI_MODEL_VISION],
            temp_query=self.config.data[self.config.OPENAI_TEMP_QUERY],
            chunk_lines_block=self.config.data[self.config.CHUNK_LINES_BLOCK],
        )

        self.qdrant = QdrantManager(
            cli=self.cli,
            ai=self.ai,
            server_url=self.config.data[self.config.QDRANT_SERVER_URL],
            collection=self.config.data[self.config.QDRANT_COLLECTION],
            vector_size=self.config.data[self.config.QDRANT_VECTOR_SIZE],
            score_min=self.config.data[self.config.QDRANT_SCORE_MIN],
            chunks_max=self.config.data[self.config.QDRANT_CHUNKS_MAX],
        )

        self.committer = CommitManager(self.watchlist, self.ai, self.qdrant)
