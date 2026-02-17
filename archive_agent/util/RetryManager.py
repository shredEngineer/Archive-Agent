#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import asyncio
import typer
import time
import requests
import traceback
import logging
from typing import Callable, Optional, Any, Dict, NoReturn

from archive_agent.ai_provider.AiProviderError import AiProviderError
from archive_agent.ai_provider.AiProviderError import AiProviderMaxTokensError

from openai import OpenAIError

from ollama import RequestError, ResponseError

from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.http.exceptions import UnexpectedResponse
from httpx import ReadTimeout, TimeoutException

logger = logging.getLogger(__name__)


class RetryManager:
    """
    Retry manager.

    Catches common exceptions from OpenAI and requests.
    """

    # Central list of retryable exceptions to avoid duplication in sync/async paths.
    _RETRY_EXCEPTIONS = (
        # AiProvider
        AiProviderError,

        # openai
        OpenAIError,

        # ollama
        RequestError, ResponseError,

        # TODO: Handle errors of any newly introduced AI providers

        # Qdrant
        ResponseHandlingException,
        UnexpectedResponse,
        ReadTimeout,
        TimeoutException,

        # low-level
        requests.exceptions.RequestException,
    )

    def __init__(
            self,
            predelay: float = 0,
            delay_min: float = 0,
            delay_max: float = 0,
            backoff_exponent: float = 0,
            retries: int = 1,
    ):
        """
        Initialize retry manager.

        :param predelay: Initial fixed delay before first attempt (in seconds).
        :param delay_min: Initial delay between attempts (in seconds).
                          If set to 0, backoff starts at 1.0 second.
        :param delay_max: Maximum backoff delay (in seconds).
        :param backoff_exponent: Exponential backoff multiplier.
        :param retries: Maximum number of attempts.
        """
        self.predelay = predelay
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.backoff_exponent = backoff_exponent
        self.retries = retries

        self.backoff_delay = self.delay_min or 1.0
        self.fail_budget = self.retries

    def reset_backoff(self) -> None:
        """
        Reset internal backoff timer and attempt counter.

        If delay_min is 0, backoff delay resets to 1.0 second.
        """
        self.backoff_delay = self.delay_min or 1.0
        self.fail_budget = self.retries

    def apply_predelay(self) -> None:
        """
        Apply fixed delay before the first attempt.
        """
        if self.predelay > 0:
            logger.debug(f"Waiting for {self.predelay} seconds (fixed predelay) …")
            time.sleep(self.predelay)

    def apply_delay(self) -> None:
        """
        Apply exponential backoff delay between attempts.
        """
        logger.warning(f"Waiting for {self.backoff_delay} seconds (exponential backoff) …")
        time.sleep(self.backoff_delay)
        self.backoff_delay = min(self.backoff_delay * self.backoff_exponent, self.delay_max)
        self.fail_budget -= 1

    async def apply_predelay_async(self) -> None:
        """
        Apply fixed delay before the first attempt asynchronously.
        """
        if self.predelay > 0:
            logger.debug(f"Waiting for {self.predelay} seconds (fixed predelay) …")
            await asyncio.sleep(self.predelay)

    async def apply_delay_async(self) -> None:
        """
        Apply exponential backoff delay between attempts asynchronously.
        """
        logger.warning(f"Waiting for {self.backoff_delay} seconds (exponential backoff) …")
        await asyncio.sleep(self.backoff_delay)
        self.backoff_delay = min(self.backoff_delay * self.backoff_exponent, self.delay_max)
        self.fail_budget -= 1

    def _compute_attempt(self) -> int:
        """
        Compute the current attempt index (1-based) for logging.
        """
        return self.retries - self.fail_budget + 1

    def _log_retry_attempt(self, e: Exception) -> None:
        """
        Log a standardized retry attempt message with stack context.
        """
        attempt = self._compute_attempt()
        logger.warning(f"Attempt {attempt} of {self.retries} failed: {e}")
        logger.debug("Retry context:\n%s", "".join(traceback.format_stack()))

    # noinspection PyMethodMayBeStatic
    def _abort(self) -> NoReturn:
        """
        Log the terminal failure and exit the process with error code 1.

        This function never returns.
        """
        logger.error("All attempts failed – not recoverable")
        raise typer.Exit(code=1)

    def retry(self, func: Callable[..., Any], kwargs: Optional[Dict[str, Any]] = None) -> Any:
        """
        Attempt to call the given function until it completes without raising an exception,
        or the maximum number of attempts is reached.

        :param func: Callable to execute with retries.
        :param kwargs: Optional keyword arguments passed to the callable.
        :return: The result returned by the callable.
        :raises typer.Exit: If all attempts raise exceptions or a non-recoverable exception occurs.
        """
        if kwargs is None:
            kwargs = dict()

        self.apply_predelay()

        while self.fail_budget > 0:
            try:
                result = func(**kwargs)
                self.reset_backoff()
                return result

            # TODO: Handle errors of any newly introduced AI providers
            except self._RETRY_EXCEPTIONS as e:
                self._log_retry_attempt(e)
                self.apply_delay()

            except AiProviderMaxTokensError:
                raise  # Non-retryable but not fatal — let callers handle gracefully

            except Exception as e:
                logger.exception(f"Uncaught Exception `{type(e).__name__}`: {e}")
                raise typer.Exit(code=1)

        self._abort()

    async def retry_async(self, func: Callable[..., Any], kwargs: Optional[Dict[str, Any]] = None) -> Any:
        """
        Asynchronous variant of :meth:`retry` using ``asyncio.sleep`` and awaiting the
        provided callable.

        :param func: Callable to execute with retries.
        :param kwargs: Optional keyword arguments passed to the callable.
        :return: The result returned by the callable.
        :raises typer.Exit: If all attempts raise exceptions or a non-recoverable exception occurs.
        """
        if kwargs is None:
            kwargs = dict()

        await self.apply_predelay_async()

        while self.fail_budget > 0:
            try:
                result = await func(**kwargs)
                self.reset_backoff()
                return result

            # TODO: Handle errors of any newly introduced AI providers
            except self._RETRY_EXCEPTIONS as e:
                self._log_retry_attempt(e)
                await self.apply_delay_async()

            except AiProviderMaxTokensError:
                raise  # Non-retryable but not fatal — let callers handle gracefully

            except Exception as e:
                logger.exception(f"Uncaught Exception `{type(e).__name__}`: {e}")
                raise typer.Exit(code=1)

        self._abort()
