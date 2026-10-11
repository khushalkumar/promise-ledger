from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import AzureOpenAI


@dataclass(frozen=True)
class AzureConfig:
    endpoint: str
    api_key: str
    deployment: str
    api_version: str

    @classmethod
    def from_env(cls) -> AzureConfig:
        names = {
            "endpoint": "PROMISE_LEDGER_AZURE_ENDPOINT",
            "api_key": "PROMISE_LEDGER_AZURE_API_KEY",
            "deployment": "PROMISE_LEDGER_AZURE_DEPLOYMENT",
            "api_version": "PROMISE_LEDGER_AZURE_API_VERSION",
        }
        values = {field: os.getenv(name) for field, name in names.items()}
        missing = [names[field] for field, value in values.items() if not value]
        if missing:
            raise ValueError(f"Missing Azure OpenAI environment variables: {', '.join(missing)}")
        return cls(**values)  # type: ignore[arg-type]


@dataclass
class TokenUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AzureJsonBackend:
    def __init__(self, config: AzureConfig, *, client: Any | None = None) -> None:
        self._deployment = config.deployment
        self._client = client or AzureOpenAI(
            api_key=config.api_key, azure_endpoint=config.endpoint, api_version=config.api_version
        )
        self.usage = TokenUsage()

    @classmethod
    def from_env(cls) -> AzureJsonBackend:
        return cls(AzureConfig.from_env())

    def complete_json(self, system: str, user: str) -> str:
        completion = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Azure OpenAI returned an empty response")
        usage = completion.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_tokens", prompt_tokens + completion_tokens)
            or prompt_tokens + completion_tokens
        )
        self.usage.calls += 1
        self.usage.prompt_tokens += prompt_tokens
        self.usage.completion_tokens += completion_tokens
        self.usage.total_tokens += total_tokens
        return content
