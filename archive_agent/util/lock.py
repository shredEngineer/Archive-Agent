#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import tempfile
import fcntl
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def file_lock(lock_name):
    """
    Decorator to apply a file-based lock to a function.
    :param lock_name: Name of the lock file (unique per function).
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            lock_path = tempfile.gettempdir() + f"/{lock_name}.lock"
            with open(lock_path, "w") as lock_file:
                logger.debug(f"Acquiring lock: {lock_path}")
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    logger.critical(f"Lock is currently held by another process. Waiting for release: {lock_path}")
                    fcntl.flock(lock_file, fcntl.LOCK_EX)  # Wait until the lock is released
                result = func(*args, **kwargs)
                logger.debug(f"Releasing lock: {lock_path}")
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                return result
        return wrapper
    return decorator
