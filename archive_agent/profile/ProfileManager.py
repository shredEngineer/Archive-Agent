#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from pathlib import Path
from copy import deepcopy
from typing import Optional

from archive_agent.core.CliManager import CliManager

from archive_agent.util.StorageManager import StorageManager

logger = logging.getLogger(__name__)


class ProfileManager(StorageManager):
    """
    Profile manager.
    """

    PROFILE_VERSION = 'profile_version'

    PROFILE_NAME = 'profile_name'

    DEFAULT_CONFIG = {
        PROFILE_VERSION: 1,
        PROFILE_NAME: "default",
    }

    def __init__(self, cli: CliManager, settings_path: Path, profile_name: Optional[str]) -> None:
        """
        Initialize profile manager.
        :param cli: CLI manager.
        :param settings_path: Settings path.
        :param profile_name: Optional profile name to create or switch to (or "" to request prompt).
        """
        self.cli = cli

        StorageManager.__init__(self, settings_path / "profile.json", deepcopy(self.DEFAULT_CONFIG))

        available_profiles = [p.name for p in settings_path.iterdir() if p.is_dir()]

        if len(available_profiles) == 0:
            logger.info("No profiles found")
            profile_name = ""  # Request prompt

        else:
            logger.info(f"Found ({len(available_profiles)}) profile(s):")
            for profile in available_profiles:
                logger.info(f"- '{profile}'")

        if profile_name is not None:
            if profile_name == "":
                profile_name = self.cli.prompt(
                    "👉 Profile to create or switch to:",
                    is_cmd=False,
                    default=self.data[self.PROFILE_NAME],
                )
            self.data[self.PROFILE_NAME] = profile_name
            self.save()

    def upgrade(self) -> bool:
        """
        Upgrade data.
        :return: True if data upgraded, False otherwise.
        """
        return False

    def validate(self) -> bool:
        """
        Validate data.
        :return: True if data is valid, False otherwise.
        """
        return True

    def get_profile_name(self) -> str:
        """
        Get profile name.
        :return: Profile name:
        """
        return self.data[self.PROFILE_NAME]
