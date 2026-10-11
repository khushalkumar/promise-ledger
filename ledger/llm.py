from __future__ import annotations

import os
from dataclasses import dataclass

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


class AzureJsonBackend:
    def __init__(self, config: AzureConfig) -> None:
        self._deployment = config.deployment
        self._client = AzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.endpoint,
            api_version=config.api_version,
        )

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
        return content
