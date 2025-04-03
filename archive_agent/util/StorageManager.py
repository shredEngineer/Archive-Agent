#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import json
import shutil
from pathlib import Path
from copy import deepcopy
from typing import Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StorageManager(ABC):
    """
    Storage manager.
    """

    def __init__(self, file_path: Path, default: Dict[str, Any]) -> None:
        """
        Initialize storage manager.
        :param file_path: File path.
        :param default: Default data.
        """
        self.file_path = file_path
        self.default = default

        self.data: Dict[str, Any] = {}

        self.load_or_create()

    def load_or_create(self) -> None:
        """
        Load or create file.
        """
        try:
            if not self.file_path.exists():
                self.create()
            else:
                self.load()
        except Exception as e:
            logger.error(f"Failed to load file: '{self.file_path}': {e}")
            raise typer.Exit(code=1)

    def create(self) -> None:
        """
        Create file.
        """
        self.data = deepcopy(self.default)
        self.save()
        logger.info(f"Created default file: '{self.file_path}'")

    def load(self) -> None:
        """
        Load file.
        """
        with open(self.file_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        missing_keys = self.default.keys() - self.data.keys()
        if missing_keys:
            logger.error(f"Missing keys in file: '{self.file_path}': {missing_keys}")
            raise typer.Exit(code=1)

        if not self.validate():
            logger.error(f"Invalid data in file: '{self.file_path}'")
            raise typer.Exit(code=1)

        logger.debug(f"Loaded existing file: '{self.file_path}'")

    def save(self) -> None:
        """
        Save file (atomic write).
        """
        if not self.validate():
            logger.error(f"Invalid data in file: '{self.file_path}'")
            raise typer.Exit(code=1)

        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self.file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            # noinspection PyTypeChecker
            json.dump(self.data, f, indent=4)
        shutil.move(temp_path, self.file_path)

        logger.debug(f"Saved file: '{self.file_path}'")

    @abstractmethod
    def validate(self) -> bool:
        """
        Validate data.
        :return: True if data is valid, False otherwise.
        """
        raise NotImplementedError
