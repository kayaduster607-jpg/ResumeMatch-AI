"""LLM client abstraction.

Supports:
- mock: rule-based local fallback
- openai: OpenAI API
- deepseek: DeepSeek using OpenAI-compatible API
- openai_compatible: any OpenAI-compatible endpoint
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.core.config import get_settings
from app.core.exceptions import LLMCallError


class BaseLLMClient(ABC):
    provider_name: str = "base"
    model: str = ""

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Send a chat completion request and return the assistant's reply."""
        ...

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Any:
        """Call chat() and parse the response as JSON object or array."""
        raw = self.chat(system_prompt, user_prompt, temperature=temperature)
        return extract_json_value(raw)


class MockLLMClient(BaseLLMClient):
    provider_name = "mock"
    model = "rule-based"

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        return "{}"


class OpenAICompatibleLLMClient(BaseLLMClient):
    def __init__(self) -> None:
        settings = get_settings()
        provider = (settings.LLM_PROVIDER or "mock").strip().lower()

        if provider == "deepseek":
            api_key = settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
            base_url = settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com/v1"
            model = settings.DEEPSEEK_MODEL or settings.LLM_MODEL or "deepseek-chat"
        else:
            api_key = settings.OPENAI_API_KEY or settings.DEEPSEEK_API_KEY
            base_url = settings.OPENAI_BASE_URL or settings.DEEPSEEK_BASE_URL
            model = settings.LLM_MODEL or settings.DEEPSEEK_MODEL

        if not api_key:
            raise LLMCallError(
                f"LLM_PROVIDER={provider}，但没有配置 API Key。请在 backend/.env 设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。"
            )
        if not base_url:
            raise LLMCallError("没有配置 OPENAI_BASE_URL / DEEPSEEK_BASE_URL。")
        if not model:
            raise LLMCallError("没有配置 LLM_MODEL / DEEPSEEK_MODEL。")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMCallError("缺少 openai 包。请执行：python -m pip install -r requirements.txt") from exc

        self.provider_name = provider
        self.model = model
        self.base_url = base_url
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            raise LLMCallError(f"{self.provider_name} API 调用失败：{exc}") from exc


_client_instance: Optional[BaseLLMClient] = None
_client_key: Optional[tuple[str, str, str]] = None


def is_real_llm_enabled() -> bool:
    provider = (get_settings().LLM_PROVIDER or "mock").strip().lower()
    return provider not in {"", "mock", "rule", "rules", "local"}


def get_llm_client() -> BaseLLMClient:
    global _client_instance, _client_key
    settings = get_settings()
    provider = (settings.LLM_PROVIDER or "mock").strip().lower()

    # Recreate the singleton if provider/model changed during a dev restart.
    if provider == "deepseek":
        key = (provider, settings.DEEPSEEK_BASE_URL, settings.DEEPSEEK_MODEL)
    else:
        key = (provider, settings.OPENAI_BASE_URL, settings.LLM_MODEL)

    if _client_instance is not None and _client_key == key:
        return _client_instance

    if provider in {"", "mock", "rule", "rules", "local"}:
        _client_instance = MockLLMClient()
    elif provider in {"openai", "deepseek", "openai_compatible", "compatible"}:
        _client_instance = OpenAICompatibleLLMClient()
    else:
        raise LLMCallError(
            f"不支持的 LLM_PROVIDER={provider}。可用值：mock / openai / deepseek / openai_compatible。"
        )
    _client_key = key
    return _client_instance


def get_llm_status() -> dict[str, Any]:
    settings = get_settings()
    provider = (settings.LLM_PROVIDER or "mock").strip().lower()
    client = get_llm_client()
    return {
        "provider": provider,
        "model": getattr(client, "model", ""),
        "real_llm_enabled": is_real_llm_enabled(),
        "strict_mode": bool(settings.LLM_STRICT_MODE),
    }


def extract_json_value(text: str) -> Any:
    """Parse JSON object or array from an LLM response.

    Handles markdown fences and extra explanatory text.
    """
    candidate = (text or "").strip()
    if not candidate:
        raise LLMCallError("LLM 返回为空，无法解析 JSON。")

    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Object first, then array.
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, candidate, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    raise LLMCallError("无法从 LLM 返回中解析 JSON。请检查模型是否按要求只返回 JSON。")
