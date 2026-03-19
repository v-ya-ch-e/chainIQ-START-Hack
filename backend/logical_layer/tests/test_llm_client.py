"""Tests for the LLM client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.clients.llm import LLMClient


class SampleResponse(BaseModel):
    name: str = ""
    value: int = 0


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_structured_call_success(self):
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.input = {"name": "test", "value": 42}

        response = MagicMock()
        response.content = [tool_block]

        mock_anthropic = MagicMock()
        mock_anthropic.messages.create = AsyncMock(return_value=response)

        client = LLMClient(api_key="test-key", model="test-model")
        client.client = mock_anthropic

        result, fallback = await client.structured_call(
            system_prompt="test",
            user_prompt="test",
            response_model=SampleResponse,
        )

        assert result is not None
        assert result.name == "test"
        assert result.value == 42
        assert fallback is False

    @pytest.mark.asyncio
    async def test_structured_call_no_tool_block(self):
        text_block = MagicMock()
        text_block.type = "text"

        response = MagicMock()
        response.content = [text_block]

        mock_anthropic = MagicMock()
        mock_anthropic.messages.create = AsyncMock(return_value=response)

        client = LLMClient(api_key="test-key", model="test-model")
        client.client = mock_anthropic

        result, fallback = await client.structured_call(
            system_prompt="test",
            user_prompt="test",
            response_model=SampleResponse,
        )

        assert result is None
        assert fallback is True

    @pytest.mark.asyncio
    async def test_structured_call_api_error(self):
        mock_anthropic = MagicMock()
        mock_anthropic.messages.create = AsyncMock(
            side_effect=Exception("API rate limit")
        )

        client = LLMClient(api_key="test-key", model="test-model")
        client.client = mock_anthropic

        result, fallback = await client.structured_call(
            system_prompt="test",
            user_prompt="test",
            response_model=SampleResponse,
        )

        assert result is None
        assert fallback is True

    @pytest.mark.asyncio
    async def test_structured_call_invalid_schema(self):
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.input = {"invalid_field": "oops"}

        response = MagicMock()
        response.content = [tool_block]

        mock_anthropic = MagicMock()
        mock_anthropic.messages.create = AsyncMock(return_value=response)

        client = LLMClient(api_key="test-key", model="test-model")
        client.client = mock_anthropic

        result, fallback = await client.structured_call(
            system_prompt="test",
            user_prompt="test",
            response_model=SampleResponse,
        )

        # Pydantic allows extra fields by default and uses defaults
        assert result is not None
        assert result.name == ""
        assert result.value == 0
