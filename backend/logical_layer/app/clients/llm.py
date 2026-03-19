"""Async Anthropic LLM client with structured output via tool_use."""

from __future__ import annotations

import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Wraps anthropic.AsyncAnthropic for structured output calls."""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int = 2000,
    ) -> tuple[T | None, bool]:
        """
        Call Claude with tool_use for structured output.

        Returns (parsed_result, used_fallback).
        If LLM fails, returns (None, True).
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[
                    {
                        "name": "structured_output",
                        "description": "Return structured data matching the required schema.",
                        "input_schema": response_model.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": "structured_output"},
            )
            tool_block = next(
                b for b in response.content if b.type == "tool_use"
            )
            result = response_model.model_validate(tool_block.input)
            return result, False
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None, True
