#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import json
import shutil
from pathlib import Path
from typing import Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StorageManager(ABC):
    """
    Storage manager.
    """

    def __init__(self, filename: Path, default: Dict[str, Any]) -> None:
        """
        Initialize storage manager.
        :param filename: Filename.
        :param default: Default data.
        """
        self.filename = filename
        self.default = default

        self.data: Dict[str, Any] = {}

        self.load_or_create()

    def load_or_create(self) -> None:
        """
        Load or create file.
        """
        try:
            if not self.filename.exists():
                self.create()
            else:
                self.load()
        except Exception as e:
            logger.error(f"Failed to load file: '{self.filename}': {e}")
            raise typer.Exit(code=1)

    def create(self) -> None:
        """
        Create file.
        """
        self.data = self.default
        self.save()
        logger.info(f"Created default file: '{self.filename}'")

    def load(self) -> None:
        """
        Load file.
        """
        with open(self.filename, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        missing_keys = self.default.keys() - self.data.keys()
        if missing_keys:
            logger.error(f"Missing keys in file: '{self.filename}': {missing_keys}")
            raise typer.Exit(code=1)

        if not self.validate():
            logger.error(f"Invalid data in file: '{self.filename}'")
            raise typer.Exit(code=1)

        logger.debug(f"Loaded existing file: '{self.filename}'")

    def save(self) -> None:
        """
        Save file (atomic write).
        """
        if not self.validate():
            logger.error(f"Invalid data in file: '{self.filename}'")
            raise typer.Exit(code=1)

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self.filename.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            # noinspection PyTypeChecker
            json.dump(self.data, f, indent=4)
        shutil.move(temp_path, self.filename)

        logger.debug(f"Saved file: '{self.filename}'")

    @abstractmethod
    def validate(self) -> bool:
        """
        Validate data.
        :return: True if data is valid, False otherwise.
        """
        raise NotImplementedError
