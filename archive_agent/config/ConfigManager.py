# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import json
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Config manager.
    """

    DEFAULT_CONFIG = {
        "model": "text-embedding-3-small",
        "collection_name": "archive-agent",
        "qdrant_url": "http://localhost:6333"
    }

    def __init__(self) -> None:
        """
        Initialize config manager.
        """
        self.config_path = Path.home() / ".archive-agent-settings" / "config.json"
        self.config: dict[str, Any] = {}
        self.load_or_create()

    def load_or_create(self) -> None:
        """
        Load or create config.
        """
        try:
            if self.config_path.exists():
                self.load()
            else:
                self.create()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise typer.Exit(code=1)

    def create(self) -> None:
        """
        Create config.
        """
        self.config = self.DEFAULT_CONFIG
        self.save()
        logger.info("Created default config")

    def load(self) -> None:
        """
        Load config.
        """
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        missing_keys = self.DEFAULT_CONFIG.keys() - self.config.keys()
        if missing_keys:
            raise RuntimeError(f"Missing keys in watchlist: {missing_keys}")
        logger.debug("Loaded existing config")

    def save(self) -> None:
        """
        Save config to disk in atomic write.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.config_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            # noinspection PyTypeChecker
            json.dump(self.config, f, indent=4)
        shutil.move(temp_path, self.config_path)
        logger.debug("Saved config")
