#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import Optional, Any
from diskcache import Cache
from pathlib import Path

from archive_agent.core.CliManager import CliManager


class CacheManager:
    """
    Cache manager.
    """

    def __init__(self, cli: CliManager, cache_path: Path, invalidate_cache: bool = False, verbose: bool = False) -> None:
        """
        Initialize cache manager.
        :param cli: CLI manager.
        :param cache_path: Cache path.
        :param invalidate_cache: Invalidate cache if enabled, probe cache otherwise.
        :param verbose: Verbosity switch.
        """
        self.cli = cli
        self.cache_path = cache_path
        self.invalidate_cache = invalidate_cache
        self.verbose = verbose

        existed = (self.cache_path.exists() and any(self.cache_path.iterdir()))

        self.cache = Cache(self.cache_path.__str__())

        if existed:
            self.cli.logger.info(f"Loaded cache at {self.cache_path}")
        else:
            self.cli.logger.info(f"Created cache at {self.cache_path}")

    def get(self, key: str, display_key: str) -> Optional[Any]:
        """
        Get value from cache.
        :param key: Key.
        :param display_key: Display key (human-readable).
        :return: Value.
        """
        if self.invalidate_cache:
            if self.verbose:
                self.cli.logger.info(f"Cache read bypassed (--nocache) for '{display_key}'")
            return None

        if key in self.cache:
            if self.verbose:
                self.cli.logger.info(f"Cache hit for '{display_key}'")
            return self.cache[key]
        else:
            if self.verbose:
                self.cli.logger.info(f"Cache miss for '{display_key}'")
            return None

    def __contains__(self, key):
        return key in self.cache

    def __getitem__(self, key):
        return self.cache[key]

    def __setitem__(self, key, value):
        self.cache[key] = value

    def __delitem__(self, key):
        del self.cache[key]
