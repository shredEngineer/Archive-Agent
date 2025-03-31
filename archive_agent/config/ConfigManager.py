#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from pathlib import Path

from archive_agent.util import StorageManager

logger = logging.getLogger(__name__)


class ConfigManager(StorageManager):
    """
    Config manager.
    """

    DEFAULT_CONFIG = {
        'openai_model_embed': "text-embedding-3-small",
        'openai_model_query': "gpt-4o-2024-08-06",
        'qdrant_collection': "archive-agent",
        'qdrant_server_url': "http://localhost:6333"
    }

    def __init__(self, profile_path: Path) -> None:
        """
        Initialize config manager.
        :param profile_path: Profile path.
        """
        StorageManager.__init__(self, profile_path / "config.json", self.DEFAULT_CONFIG)

    def validate(self) -> bool:
        """
        Validate data.
        :return: True if data is valid, False otherwise.
        """
        return True
