# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import json
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WatchlistManager:
    """
    Watchlist manager.
    """

    DEFAULT_WATCHLIST = {
        "watched": [],
        "unwatched": [],
        "state": [],
    }

    def __init__(self) -> None:
        """
        Initialize watchlist manager.
        """
        self.watchlist_path = Path.home() / ".archive-agent-settings" / "watchlist.json"
        self.watchlist: dict[str, Any] = {}
        self.load_or_create()

    def load_or_create(self) -> None:
        """
        Load or create watchlist.
        """
        try:
            if self.watchlist_path.exists():
                self.load()
            else:
                self.create()
        except Exception as e:
            logger.error(f"Failed to load watchlist: {e}")
            raise typer.Exit(code=1)

    def create(self) -> None:
        """
        Create watchlist.
        """
        self.watchlist = self.DEFAULT_WATCHLIST
        self.save()
        logger.info("Created default watchlist")

    def load(self) -> None:
        """
        Load watchlist.
        """
        with open(self.watchlist_path, "r", encoding="utf-8") as f:
            self.watchlist = json.load(f)
        missing_keys = self.DEFAULT_WATCHLIST.keys() - self.watchlist.keys()
        if missing_keys:
            raise RuntimeError(f"Missing keys in watchlist: {missing_keys}")
        logger.debug("Loaded existing watchlist")

    def save(self) -> None:
        """
        Save watchlist to disk in atomic write.
        """
        self.watchlist_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.watchlist_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            # noinspection PyTypeChecker
            json.dump(self.watchlist, f, indent=4)
        shutil.move(temp_path, self.watchlist_path)
        logger.debug("Saved watchlist")
