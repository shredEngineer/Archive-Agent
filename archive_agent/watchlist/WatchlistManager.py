#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import os
from pathlib import Path
from copy import deepcopy
from typing import Dict, Any

from archive_agent.data.FileData import FileData
from archive_agent.util.StorageManager import StorageManager
from archive_agent.util.format import format_file
from archive_agent.util.pattern import validate_pattern, resolve_pattern

logger = logging.getLogger(__name__)


TrackedFiles = Dict[str, Dict[str, Any]]  # {file_path: file_meta}


class WatchlistManager(StorageManager):
    """
    Watchlist manager.
    """

    WATCHLIST_VERSION = 'watchlist_version'

    DEFAULT_WATCHLIST = {
        WATCHLIST_VERSION: 2,
        'included': [],
        'excluded': [],
        'tracked': {},
    }

    DIFF_NONE = 'None'
    DIFF_ADDED = 'added'
    DIFF_REMOVED = 'removed'
    DIFF_CHANGED = 'changed'
    DIFF_OPTIONS = [DIFF_NONE, DIFF_ADDED, DIFF_REMOVED, DIFF_CHANGED]

    def __init__(self, profile_path: Path) -> None:
        """
        Initialize watchlist manager.
        :param profile_path: Profile path.
        """
        StorageManager.__init__(self, profile_path / "watchlist.json", deepcopy(self.DEFAULT_WATCHLIST))

    def upgrade(self) -> bool:
        """
        Upgrade data.
        :return: True if data upgraded, False otherwise.
        """
        upgraded = False

        version = self.data.get(self.WATCHLIST_VERSION, 1)

        if version < 2:
            logger.warning(f"Upgrading watchlist (v2): {format_file(self.file_path)}")
            self.data[self.WATCHLIST_VERSION] = 2
            upgraded = True

        return upgraded

    def validate(self) -> bool:
        """
        Validate data.
        :return: True if data is valid, False otherwise.
        """
        if set(self.data['included']) & set(self.data['excluded']):
            logger.error("Overlapping included and excluded patterns")
            return False

        if any(file_meta['diff'] not in self.DIFF_OPTIONS for file_meta in self.data['tracked'].values()):
            logger.error("Invalid diff option encountered")
            return False

        return True

    def include(self, pattern) -> None:
        """
        Add included pattern.
        :param pattern: Pattern.
        """
        pattern = validate_pattern(pattern)

        if pattern in self.data['included']:
            logger.info(f"Already included pattern:")
            logger.info(f"- {pattern}")

        elif pattern in self.data['excluded']:
            logger.info(f"Included previously excluded pattern:")
            logger.info(f"- {pattern}")
            self.data['excluded'].remove(pattern)
            self.data['included'] = list(set(self.data['included']) | {pattern})
            self.save()

        else:
            logger.info(f"New included pattern:")
            logger.info(f"- {pattern}")
            self.data['included'] = list(set(self.data['included']) | {pattern})
            self.save()

    def exclude(self, pattern) -> None:
        """
        Add excluded pattern.
        :param pattern: Pattern.
        """
        pattern = validate_pattern(pattern)

        if pattern in self.data['excluded']:
            logger.info(f"Already excluded pattern:")
            logger.info(f"- {pattern}")

        elif pattern in self.data['included']:
            logger.info(f"Excluded previously included pattern:")
            logger.info(f"- {pattern}")
            self.data['included'].remove(pattern)
            self.data['excluded'] = list(set(self.data['excluded']) | {pattern})
            self.save()

        else:
            logger.info(f"New excluded pattern:")
            logger.info(f"- {pattern}")
            self.data['excluded'] = list(set(self.data['excluded']) | {pattern})
            self.save()

    def remove(self, pattern) -> None:
        """
        Remove previously included / excluded pattern.
        :param pattern: Pattern.
        """
        pattern = validate_pattern(pattern)

        if pattern in self.data['included']:
            logger.info(f"Removed included pattern:")
            logger.info(f"- {pattern}")
            self.data['included'].remove(pattern)
            self.save()

        elif pattern in self.data['excluded']:
            logger.info(f"Removed excluded pattern:")
            logger.info(f"- {pattern}")
            self.data['excluded'].remove(pattern)
            self.save()

        else:
            logger.warning(f"No existing rule for pattern:")
            logger.info(f"{pattern}")

    def patterns(self) -> None:
        """
        Show the list of included / excluded patterns.
        """
        if len(self.data['included']) > 0:
            logger.info(f"({len(self.data['included'])}) included pattern(s):")
            for included_pattern in self.data['included']:
                logger.info(f"- {included_pattern}")
        else:
            logger.info("(0) included pattern(s)")

        if len(self.data['excluded']) > 0:
            logger.info(f"({len(self.data['excluded'])}) excluded pattern(s):")
            for excluded_pattern in self.data['excluded']:
                logger.info(f"- {excluded_pattern}")
        else:
            logger.info("(0) excluded pattern(s)")

    def get_included_patterns(self) -> list[str]:
        """
        Get the list of included patterns.
        :return: List of included patterns.
        """
        return self.data['included']

    def get_excluded_patterns(self) -> list[str]:
        """
        Get the list of excluded patterns.
        :return: List of excluded patterns.
        """
        return self.data['excluded']

    def track(self):
        """
        Resolve all patterns and track changed files.
        """
        logger.info(f"Resolving ({len(self.data['included'])}) included / "
                    f"({len(self.data['excluded'])}) excluded pattern(s):")

        included_files = []
        for included_pattern in self.data['included']:
            included_files += resolve_pattern(included_pattern)
        included_files = list(set(included_files))
        logger.info(f"Matched ({len(included_files)}) unique included file(s)")

        excluded_files = []
        for excluded_pattern in self.data['excluded']:
            excluded_files += resolve_pattern(excluded_pattern)
        excluded_files = list(set(excluded_files))
        logger.info(f"Matched ({len(excluded_files)}) unique excluded file(s)")

        tracked_files_old = self.data['tracked'].keys()
        tracked_files_new = sorted([file for file in included_files if file not in excluded_files])

        logger.info(f"Ignoring ({len(included_files) - len(tracked_files_new)}) file(s)")

        logger.info(f"Tracking ({len(tracked_files_new)}) file(s):")

        added_files = [file for file in tracked_files_new if file not in tracked_files_old]
        removed_files = [file for file in tracked_files_old if file not in tracked_files_new]

        possibly_changed_files = [file for file in tracked_files_new if file not in added_files + removed_files]

        tracked_dict_old = self.data['tracked']
        tracked_dict_new = {
            file: {
                'size': os.path.getsize(file),
                'mtime': os.path.getmtime(file),
                'diff': self.DIFF_NONE,
            }
            for file in tracked_files_new
        }

        changed_files = [file for file in possibly_changed_files if tracked_dict_new[file] != tracked_dict_old[file]]

        for file in added_files:
            tracked_dict_new[file]['diff'] = self.DIFF_ADDED

        for file in removed_files:
            tracked_dict_new[file] = {
                'size': 0,
                'mtime': 0,
                'diff': self.DIFF_REMOVED,
            }

        for file in changed_files:
            tracked_dict_new[file]['diff'] = self.DIFF_CHANGED

        unchanged_count = len(tracked_files_new) - len(added_files) - len(changed_files)

        logger.info(f"({len(added_files)}) added file(s)")
        logger.info(f"({len(removed_files)}) removed file(s)")
        logger.info(f"({len(changed_files)}) changed file(s)")
        logger.info(f"({unchanged_count}) unchanged file(s)")

        self.data['tracked'] = tracked_dict_new
        self.save()

    def get_tracked_files(self) -> TrackedFiles:
        """
        Get the list of tracked files.
        :return: List of tracked files.
        """
        return self.data['tracked']

    def list(self) -> None:
        """
        Show the list of tracked files.
        """
        if len(self.data['tracked']) > 0:
            logger.info(f"({len(self.data['tracked'])}) tracked files(s):")
            for file in self.data['tracked'].keys():
                logger.info(f"- {file}")
        else:
            logger.info("(0) tracked file(s)")

    def get_diff_files(self, diff_option: str) -> TrackedFiles:
        """
        Get the list of tracked files filtered by diff option.
        :param diff_option: Diff option.
        :return: List of tracked files filtered by diff option.
        """
        return {
            file_path: file_meta
            for file_path, file_meta in self.data['tracked'].items()
            if file_meta['diff'] == diff_option
        }

    def diff(self) -> None:
        """
        Show the list of changed files.
        """
        added_files = self.get_diff_files(self.DIFF_ADDED)
        changed_files = self.get_diff_files(self.DIFF_CHANGED)
        removed_files = self.get_diff_files(self.DIFF_REMOVED)

        if len(added_files) > 0:
            logger.info(f"({len(added_files)}) added files(s):")
            for file in added_files.keys():
                logger.info(f"- ADDED    {file}")
        else:
            logger.info("(0) added file(s)")

        if len(changed_files) > 0:
            logger.info(f"({len(changed_files)}) changed files(s):")
            for file in changed_files.keys():
                logger.info(f"- CHANGED  {file}")
        else:
            logger.info("(0) changed file(s)")

        if len(removed_files) > 0:
            logger.info(f"({len(removed_files)}) removed files(s):")
            for file in removed_files.keys():
                logger.info(f"- REMOVED  {file}")
        else:
            logger.info("(0) removed file(s)")

    def diff_mark_resolved(self, file_data: FileData) -> None:
        """
        Mark file in diff as resolved.
        If the file was deleted, untrack it completely.
        :param file_data: File data.
        """
        if file_data.file_path not in self.data['tracked']:
            logger.error(f"Untracked {format_file(file_data.file_path)}")
            raise typer.Exit(code=1)

        if self.data['tracked'][file_data.file_path]['diff'] == self.DIFF_NONE:
            logger.error(f"Already marked as resolved: {format_file(file_data.file_path)}")
            raise typer.Exit(code=1)

        if self.data['tracked'][file_data.file_path]['diff'] == self.DIFF_REMOVED:
            del self.data['tracked'][file_data.file_path]
        else:
            self.data['tracked'][file_data.file_path]['diff'] = self.DIFF_NONE

        self.save()
