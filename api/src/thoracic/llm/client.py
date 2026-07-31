from __future__ import annotations

import asyncio
import json

import httpx

from thoracic.config import settings
from .errors import (
    LlmAuthError,
    LlmError,
    LlmJsonParseError,
    LlmRateLimitError,
    LlmServerError,
)


class MiniMaxClient:
    """MiniMax M3 OpenAI 兼容 Chat Completions 客户端。

    异步 httpx + asyncio.Semaphore 并发控制 + 指数退避重试。
    默认从 `thoracic.config.settings` 注入;构造参数可显式覆盖,便于单测。
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_concurrent: int | None = None,
    ):
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self.semaphore = asyncio.Semaphore(
            max_concurrent or settings.LLM_MAX_CONCURRENT
        )

    def _url(self) -> str:
        return f"{self.base_url}/chat/completions"

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.2,
        response_format: dict | None = None,
        max_retries: int = 3,
    ) -> dict:
        """一次 chat 调用,返回完整 JSON 响应(包含 choices[0].message.content)。"""
        if not self.api_key:
            raise LlmAuthError("LLM_API_KEY not configured")

        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            body["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(max_retries):
                try:
                    async with self.semaphore:
                        r = await client.post(
                            self._url(), json=body, headers=headers
                        )
                    if r.status_code == 401 or r.status_code == 403:
                        raise LlmAuthError(
                            f"HTTP {r.status_code}: {r.text[:200]}"
                        )
                    if r.status_code == 429:
                        last_exc = LlmRateLimitError("429 rate limit")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2**attempt)
                            continue
                        raise last_exc
                    if r.status_code >= 500:
                        last_exc = LlmServerError(
                            f"HTTP {r.status_code}: {r.text[:200]}"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2**attempt)
                            continue
                        raise last_exc
                    r.raise_for_status()
                    return r.json()
                except (httpx.TransportError, httpx.HTTPStatusError) as e:
                    last_exc = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise LlmError(f"transport failed: {e}") from e

        # 防御性:理论上 for 循环总会 raise 或 return;到这里说明被吞掉了。
        raise LlmError(
            f"chat failed after {max_retries} retries: {last_exc}"
        )

    async def chat_json(self, messages: list[dict], **kwargs) -> dict:
        """便捷方法:强制 `response_format={"type":"json_object"}`,并返回 message.content 的 dict。

        返回的是 `json.loads(response["choices"][0]["message"]["content"])` 结果。
        """
        kwargs.setdefault("response_format", {"type": "json_object"})
        response = await self.chat(messages, **kwargs)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LlmJsonParseError(
                f"unusual response shape: {response}"
            ) from e
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LlmJsonParseError(
                f"content not JSON: {content[:200]}"
            ) from e


# 模块级默认 client(从 settings 读)。无 API key 时不会立即报错,首次 chat 才 raise。
default_client = MiniMaxClient()
