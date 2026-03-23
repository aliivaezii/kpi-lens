"""Unit tests for the LLM client wrapper."""

from __future__ import annotations

import types
from unittest.mock import MagicMock

import pytest

from kpi_lens.llm.client import LLMClient, LLMError


def _make_fake_anthropic(
    side_effect: object = None,
    text: str = "Mock response text.",
) -> tuple[types.SimpleNamespace, MagicMock]:
    """
    Return (fake_anthropic_module, mock_messages_client).

    Patching the whole `anthropic` namespace in client.py lets us control
    what `anthropic.RateLimitError` and `anthropic.APIStatusError` resolve to,
    which is necessary for the except clauses to catch our fake exceptions.
    """

    class FakeRateLimitError(Exception):
        pass

    class FakeAPIStatusError(Exception):
        def __init__(self, msg: str, status_code: int = 500) -> None:
            self.status_code = status_code
            self.message = msg
            super().__init__(msg)

    mock_client = MagicMock()
    if side_effect is not None:
        mock_client.messages.create.side_effect = side_effect
    else:
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=text)],
            usage=MagicMock(input_tokens=10, output_tokens=5),
        )

    fake_module = types.SimpleNamespace(
        Anthropic=lambda **_: mock_client,
        RateLimitError=FakeRateLimitError,
        APIStatusError=FakeAPIStatusError,
    )
    return fake_module, mock_client


def test_complete_returns_string_on_success(mock_anthropic: MagicMock) -> None:
    client = LLMClient()
    result = client.complete(
        system="You are a supply chain analyst.",
        messages=[{"role": "user", "content": "What is OTIF?"}],
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_complete_calls_anthropic_with_correct_model(mock_anthropic: MagicMock) -> None:
    client = LLMClient()
    client.complete(
        system="sys",
        messages=[{"role": "user", "content": "hello"}],
    )
    mock_anthropic.messages.create.assert_called_once()
    call_kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert "model" in call_kwargs
    assert "messages" in call_kwargs


def test_complete_retries_on_rate_limit_and_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0
    fake_module, mock_client = _make_fake_anthropic()

    class FakeRateLimitError(Exception):
        pass

    fake_module.RateLimitError = FakeRateLimitError

    def side_effect(**kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise FakeRateLimitError("rate limited")
        return MagicMock(
            content=[MagicMock(text="success after retry")],
            usage=MagicMock(input_tokens=10, output_tokens=5),
        )

    mock_client.messages.create.side_effect = side_effect
    monkeypatch.setattr("kpi_lens.llm.client.anthropic", fake_module)
    monkeypatch.setattr("kpi_lens.llm.client.time.sleep", lambda _: None)

    client = LLMClient()
    result = client.complete(system="sys", messages=[{"role": "user", "content": "hi"}])
    assert result == "success after retry"
    assert call_count == 3


def test_complete_raises_llm_error_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module, mock_client = _make_fake_anthropic()

    class FakeRateLimitError(Exception):
        pass

    fake_module.RateLimitError = FakeRateLimitError
    mock_client.messages.create.side_effect = FakeRateLimitError("always rate limited")
    monkeypatch.setattr("kpi_lens.llm.client.anthropic", fake_module)
    monkeypatch.setattr("kpi_lens.llm.client.time.sleep", lambda _: None)

    client = LLMClient()
    with pytest.raises(LLMError, match="retries"):
        client.complete(system="sys", messages=[{"role": "user", "content": "hi"}])


def test_complete_raises_llm_error_on_4xx_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module, mock_client = _make_fake_anthropic()

    class FakeAPIStatusError(Exception):
        def __init__(self, msg: str, status_code: int = 400) -> None:
            self.status_code = status_code
            self.message = msg
            super().__init__(msg)

    fake_module.APIStatusError = FakeAPIStatusError
    mock_client.messages.create.side_effect = FakeAPIStatusError(
        "invalid request", status_code=400
    )
    monkeypatch.setattr("kpi_lens.llm.client.anthropic", fake_module)

    client = LLMClient()
    with pytest.raises(LLMError, match="400"):
        client.complete(system="sys", messages=[{"role": "user", "content": "hi"}])


def test_complete_retries_on_5xx_status(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0
    fake_module, mock_client = _make_fake_anthropic()

    class FakeAPIStatusError(Exception):
        def __init__(self, msg: str, status_code: int = 500) -> None:
            self.status_code = status_code
            self.message = msg
            super().__init__(msg)

    fake_module.APIStatusError = FakeAPIStatusError

    def side_effect(**kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise FakeAPIStatusError("server error", status_code=503)
        return MagicMock(
            content=[MagicMock(text="recovered")],
            usage=MagicMock(input_tokens=5, output_tokens=5),
        )

    mock_client.messages.create.side_effect = side_effect
    monkeypatch.setattr("kpi_lens.llm.client.anthropic", fake_module)
    monkeypatch.setattr("kpi_lens.llm.client.time.sleep", lambda _: None)

    client = LLMClient()
    result = client.complete(system="sys", messages=[{"role": "user", "content": "hi"}])
    assert result == "recovered"


def test_llm_error_is_exception_subclass() -> None:
    err = LLMError("something went wrong")
    assert isinstance(err, Exception)
    assert str(err) == "something went wrong"
