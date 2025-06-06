#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import click
import logging
import hashlib
import os.path
from pathlib import Path
from typing import Optional, Any, Dict

from archive_agent.config.DecoderSettings import OcrStrategy

from archive_agent.ai_provider.AiProviderKeys import AiProviderKeys
from archive_agent.ai_provider.ai_provider_registry import ai_provider_registry

from archive_agent.util.CliManager import CliManager
from archive_agent.util.format import format_file

from archive_agent.util.StorageManager import StorageManager

logger = logging.getLogger(__name__)


class ConfigManager(StorageManager, AiProviderKeys):
    """
    Config manager.
    """

    CONFIG_VERSION = 'config_version'

    QDRANT_SERVER_URL = 'qdrant_server_url'
    QDRANT_COLLECTION = 'qdrant_collection'
    QDRANT_SCORE_MIN = 'qdrant_score_min'
    QDRANT_CHUNKS_MAX = 'qdrant_chunks_max'
    CHUNK_LINES_BLOCK = 'chunk_lines_block'

    MCP_SERVER_PORT = 'mcp_server_port'

    OCR_STRATEGY = 'ocr_strategy'

    DEFAULT_CONFIG = {
        CONFIG_VERSION: 5,

        QDRANT_SERVER_URL: "http://localhost:6333",
        QDRANT_COLLECTION: "archive-agent",
        QDRANT_SCORE_MIN: .2,
        QDRANT_CHUNKS_MAX: 20,
        CHUNK_LINES_BLOCK: 50,

        MCP_SERVER_PORT: 8008,

        # deferred to `_prompt_ocr_strategy`
        OCR_STRATEGY: "",

        # deferred to `_prompt_ai_provider`
        AiProviderKeys.AI_PROVIDER: "",
        AiProviderKeys.AI_SERVER_URL: "",
        AiProviderKeys.AI_MODEL_CHUNK: "",
        AiProviderKeys.AI_MODEL_EMBED: "",
        AiProviderKeys.AI_MODEL_QUERY: "",
        AiProviderKeys.AI_MODEL_VISION: "",
        AiProviderKeys.AI_VECTOR_SIZE: 0,
        AiProviderKeys.AI_TEMPERATURE_QUERY: 0.0,
    }

    def __init__(self, cli: CliManager, settings_path: Path, profile_name: str) -> None:
        """
        Initialize config manager.
        :param cli: CLI manager.
        :param settings_path: Settings path.
        :param profile_name: Profile name.
        """
        self.cli = cli

        file_path = settings_path / profile_name / "config.json"

        if not os.path.exists(file_path):
            logger.info(f"Creating profile: '{profile_name}'")

            self._qdrant_collection_name(profile_name)
            self._prompt_ocr_strategy()
            self._prompt_ai_provider()

        else:
            logger.info(f"Using profile: '{profile_name}'")

        StorageManager.__init__(self, file_path=file_path, default=self.DEFAULT_CONFIG)

    def _qdrant_collection_name(self, profile_name: str) -> None:
        """
        Set unique Qdrant collection name.
        :param profile_name: Profile name.
        """
        profile_name_hash = hashlib.sha1(profile_name.encode('utf-8')).hexdigest()[:8]
        profile_name_safe = profile_name.replace(' ', '-')
        unique_suffix = "-" + profile_name_safe + "-" + profile_name_hash

        self.DEFAULT_CONFIG[self.QDRANT_COLLECTION] += unique_suffix

    def _prompt_ocr_strategy(self) -> None:
        """
        Prompt for OCR strategy (fill in deferred option values).
        """
        ocr_strategy_name: str = self.cli.prompt(
            "Select OCR strategy:",
            is_cmd=False,
            default=[ocr_strategy.value for ocr_strategy in OcrStrategy][0],
            type=click.Choice([ocr_strategy.value for ocr_strategy in OcrStrategy], case_sensitive=False),
            show_choices=True,
        )

        self.DEFAULT_CONFIG[self.OCR_STRATEGY] = OcrStrategy(ocr_strategy_name).value

    def _prompt_ai_provider(self) -> None:
        """
        Prompt for AI provider (fill in deferred option values).
        """
        ai_provider_name: str = self.cli.prompt(
            "Select AI provider:",
            is_cmd=False,
            default=list(ai_provider_registry.keys())[0],
            type=click.Choice(list(ai_provider_registry.keys()), case_sensitive=False),
            show_choices=True,
        )

        self.DEFAULT_CONFIG.update(ai_provider_registry[ai_provider_name]["defaults"])

    def upgrade(self) -> bool:
        """
        Upgrade data.
        :return: True if data upgraded, False otherwise.
        """
        upgraded = False

        version = self.data.get(self.CONFIG_VERSION, 1)

        # Option(s) added in v2:
        # - `ocr_mode_strict`
        if version < 2:
            self._set_version(2)
            self._add_option('ocr_mode_strict', default='false')
            upgraded = True

        # Option(s) added in v3:
        # - `mcp_server_port`
        if version < 3:
            self._set_version(3)
            self._add_option(self.MCP_SERVER_PORT)
            upgraded = True

        # Option(s) added in v4:
        # - `ai_provider`
        #
        # Option(s) renamed in v4:
        # - `openai_model_chunk`  --> `ai_model_chunk`
        # - `openai_model_embed`  --> `ai_model_embed`
        # - `openai_model_query`  --> `ai_model_query`
        # - `openai_model_vision` --> `ai_model_vision`
        # - `qdrant_vector_size`  --> `ai_vector_size`
        # - `openai_temp_query`   --> `ai_temperature_query`
        # - `ocr_mode_strict`     --> `ocr_strategy`  (is now enum instead of bool)
        if version < 4:
            self._set_version(4)
            self._add_option(self.AI_PROVIDER, default="openai")
            self._rename_option('openai_model_chunk', self.AI_MODEL_CHUNK)
            self._rename_option('openai_model_embed', self.AI_MODEL_EMBED)
            self._rename_option('openai_model_query', self.AI_MODEL_QUERY)
            self._rename_option('openai_model_vision', self.AI_MODEL_VISION)
            self._rename_option('qdrant_vector_size', self.AI_VECTOR_SIZE)
            self._rename_option('openai_temp_query', self.AI_TEMPERATURE_QUERY)
            self._rename_option('ocr_mode_strict', self.OCR_STRATEGY, translate={'false': 'relaxed', 'true': 'strict'})
            upgraded = True

        # Option(s) added in v5:
        # - `ai_server_url`
        if version < 5:
            self._set_version(5)
            ai_server_url_default = {
                "openai": "https://api.openai.com/v1",
                "ollama": "http://localhost:11434",
            }
            self._add_option(self.AI_SERVER_URL, default=ai_server_url_default[self.data[self.AI_PROVIDER]])
            upgraded = True

        return upgraded

    def _set_version(self, version: int) -> None:
        """
        Set version number.
        :param version: Version number.
        """
        logger.warning(f"Upgrading config (v{version}): {format_file(self.file_path)}")
        self.data[self.CONFIG_VERSION] = version

    def _add_option(self, key: str, default: Optional[Any] = None):
        """
        Add option.
        :param key: Option key.
        :param default: Optional default value (e.g., not from `DEFAULT_CONFIG`).
        """
        if default is not None:
            self.data[key] = default
        else:
            self.data[key] = self.DEFAULT_CONFIG[key]

    def _rename_option(self, old: str, new: str, translate: Optional[Dict[Any, Any]] = None) -> None:
        """
        Rename option.
        :param old: Old option key.
        :param new: New option key.
        :param translate: Optional translation from old value to new value.
        """
        if translate is not None:
            self.data[new] = translate[self.data[old]]
        else:
            self.data[new] = self.data[old]
        del self.data[old]

    def validate(self) -> bool:
        """
        Validate data.
        :return: True if data is valid, False otherwise.
        """
        return True
