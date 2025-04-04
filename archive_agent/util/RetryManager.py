#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import time
import requests
import traceback
import logging

logger = logging.getLogger(__name__)


class RetryManager:
    """
    Retry manager.
    """

    def __init__(
            self,
            endpoint_predelay=0,
            endpoint_delay=0,
            endpoint_timeout=0,
            endpoint_exp_backoff=0,
            endpoint_retries=1,
    ):
        """
        Initialize retry manager.
        :param endpoint_predelay: Endpoint predelay (in seconds).
        :param endpoint_delay: Endpoint delay (in seconds).
        :param endpoint_timeout: Endpoint timeout (in seconds).
        :param endpoint_exp_backoff: Endpoint exponential backoff factor.
        :param endpoint_retries: Endpoint retries.
        """
        self.endpoint_predelay = endpoint_predelay
        self.endpoint_delay = endpoint_delay
        self.endpoint_timeout = endpoint_timeout
        self.endpoint_exp_backoff = endpoint_exp_backoff
        self.endpoint_retries = endpoint_retries

        self.exp_backoff = self.endpoint_delay
        self.fail_budget = self.endpoint_retries

    def reset_backoff(self):
        self.exp_backoff = self.endpoint_delay
        self.fail_budget = self.endpoint_retries

    def predelay(self):
        if self.endpoint_predelay > 0:
            logger.debug(f"Waiting for {self.endpoint_predelay} seconds (fixed predelay) …")
            time.sleep(self.endpoint_predelay)

    def delay(self):
        logger.warning(f"Waiting for {self.exp_backoff} seconds (exponential backoff) …")
        time.sleep(self.exp_backoff)
        self.exp_backoff *= self.endpoint_exp_backoff
        self.fail_budget -= 1

    def retry(self, func, kwargs=None):
        if kwargs is None:
            kwargs = dict()
        self.predelay()

        while self.fail_budget > 0:
            result = None

            try:
                result = func(**kwargs)

            except AssertionError as e:
                logger.error(f"AssertionError – not recoverable: {e}")
                raise typer.Exit(code=1)

            except (
                    RuntimeError,
                    requests.exceptions.ReadTimeout,
            ) as e:
                if self.fail_budget > 0:
                    traceback.print_stack()
                    attempt = 1 + self.endpoint_retries - self.fail_budget
                    logger.warning(f"Recovering from attempt {attempt} of {self.endpoint_retries}: {e}")
                    self.delay()

                else:
                    logger.error(f"Network failed too many times – not recoverable: {e}")
                    raise typer.Exit(code=1)

            except Exception as e:
                logger.error(f"Uncaught Exception `{type(e).__name__}`: {e}")
                raise typer.Exit(code=1)

            if result is not None:
                self.reset_backoff()
                return result

        # TODO: Fix arriving here
        logger.error(f"This should NEVER happen – not recoverable")
        raise typer.Exit(code=1)
