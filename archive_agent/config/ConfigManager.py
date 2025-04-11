#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from pathlib import Path
from copy import deepcopy

from archive_agent.util.StorageManager import StorageManager

logger = logging.getLogger(__name__)


class ConfigManager(StorageManager):
    """
    Config manager.
    """

    OPENAI_MODEL_CHUNK = 'openai_model_chunk'
    OPENAI_MODEL_EMBED = 'openai_model_embed'
    OPENAI_MODEL_QUERY = 'openai_model_query'
    OPENAI_MODEL_VISION = 'openai_model_vision'
    OPENAI_TEMP_QUERY = 'openai_temp_query'
    QDRANT_SERVER_URL = 'qdrant_server_url'
    QDRANT_COLLECTION = 'qdrant_collection'
    QDRANT_VECTOR_SIZE = 'qdrant_vector_size'
    QDRANT_SCORE_MIN = 'qdrant_score_min'
    QDRANT_CHUNKS_MAX = 'qdrant_chunks_max'
    CHUNK_LINES_BLOCK = 'chunk_lines_block'

    DEFAULT_CONFIG = {
        OPENAI_MODEL_CHUNK: "gpt-4o-2024-08-06",
        OPENAI_MODEL_EMBED: "text-embedding-3-small",
        OPENAI_MODEL_QUERY: "gpt-4o-2024-08-06",
        OPENAI_MODEL_VISION: "gpt-4o-2024-08-06",
        OPENAI_TEMP_QUERY: 1.0,
        QDRANT_SERVER_URL: "http://localhost:6333",
        QDRANT_COLLECTION: "archive-agent",
        QDRANT_VECTOR_SIZE: 1536,
        QDRANT_SCORE_MIN: .2,
        QDRANT_CHUNKS_MAX: 20,
        CHUNK_LINES_BLOCK: 50,
    }

    def __init__(self, profile_path: Path) -> None:
        """
        Initialize config manager.
        :param profile_path: Profile path.
        """
        StorageManager.__init__(self, profile_path / "config.json", deepcopy(self.DEFAULT_CONFIG))

    def validate(self) -> bool:
        """
        Validate data.
        :return: True if data is valid, False otherwise.
        """
        return True
