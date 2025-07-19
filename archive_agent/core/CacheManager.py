#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from diskcache import Cache
from pathlib import Path

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Cache manager.
    """

    def __init__(self, cache_path: Path) -> None:
        """
        Initialize cache manager.
        :param cache_path: Cache path.
        """
        self.cache_path = cache_path

        existed = (self.cache_path.exists() and any(self.cache_path.iterdir()))

        self.cache = Cache(self.cache_path.__str__())

        if existed:
            logger.info(f"Loaded cache at {self.cache_path}")
        else:
            logger.info(f"Created cache at {self.cache_path}")

    def __contains__(self, key):
        return key in self.cache

    def __getitem__(self, key):
        return self.cache[key]

    def __setitem__(self, key, value):
        self.cache[key] = value

    def __delitem__(self, key):
        del self.cache[key]

    def pop(self) -> object:
        """
        Pop the last touched key from the cache, delete it, and return its value.
        :return: The value associated with the last touched key.
        :raises KeyError: If the cache is empty.
        """
        try:
            key = next(reversed(self.cache))
        except StopIteration:
            raise KeyError("Cache is empty.")

        value = self.cache[key]
        del self.cache[key]
        return value
