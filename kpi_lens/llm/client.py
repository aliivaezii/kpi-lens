"""
Anthropic API wrapper with retry logic and token accounting.

This is the only file that imports the `anthropic` library.
All LLM calls in the application go through this client.
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast

import anthropic
from anthropic.types import MessageParam, TextBlock

from kpi_lens.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Thin wrapper around the Anthropic SDK.

    Adds:
    - Exponential backoff retry on RateLimitError and APIStatusError (5xx)
    - Token usage logging for cost visibility
    - A structured error type so callers handle one exception, not SDK internals
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        self._model = settings.anthropic_model
        self._max_tokens = settings.anthropic_max_tokens
        self._max_retries = settings.anthropic_max_retries

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a chat-completion request and return the text response.

        Retries up to max_retries times with exponential backoff on transient errors.
        The anomaly pipeline calls this asynchronously — a failure here must never
        prevent the anomaly from being logged (callers catch LLMError).
        """
        max_tokens = max_tokens or self._max_tokens

        for attempt in range(self._max_retries):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=system,
                    # cast is safe: our callers always pass role/content dicts.
                    # The SDK's MessageParam TypedDict is structurally identical.
                    messages=cast(list[MessageParam], messages),
                )
                logger.debug(
                    "LLM call succeeded | tokens: %d in / %d out",
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )
                first = response.content[0]
                # isinstance narrows the type for mypy: the SDK content union
                # includes ThinkingBlock, ToolUseBlock, etc. that have no .text.
                # The getattr fallback handles spec-less MagicMock objects in tests
                # (isinstance returns False for them, but .text is still accessible).
                if isinstance(first, TextBlock):
                    return first.text
                return cast(str, getattr(first, "text", ""))

            except anthropic.RateLimitError:
                wait = 2**attempt
                logger.warning("Rate limited by Anthropic; retrying in %ds", wait)
                time.sleep(wait)

            except anthropic.APIStatusError as exc:
                if exc.status_code >= 500:
                    wait = 2**attempt
                    logger.warning(
                        "Anthropic 5xx error (%d); retrying in %ds",
                        exc.status_code,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    # 4xx errors (except 429) are not retryable
                    msg = f"Anthropic API error {exc.status_code}: {exc.message}"
                    raise LLMError(msg) from exc

        raise LLMError(f"LLM call failed after {self._max_retries} retries")


class LLMError(Exception):
    """Raised when the LLM API fails after all retries are exhausted."""
