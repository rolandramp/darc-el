from __future__ import annotations

import os
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


ProviderClientFactory = Callable[[str, str], Any]
SUPPORTED_PROVIDERS = {"ollama", "llama_cpp"}


class OpenAIClientService(BaseModel):
    """Create and hold OpenAI-compatible clients for Ollama and llama.cpp."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ollama_base_url: str = Field(default="http://ollama-llm:11434")
    llama_cpp_base_url: str = Field(default="http://llama-cpp-backend:8080")
    api_key: str = Field(default="")
    chat_model: str = Field(default="")
    embedding_model: str = Field(default="")
    default_provider: str = Field(default="ollama")
    client_factory: ProviderClientFactory | None = None

    _ollama_client: Any | None = PrivateAttr(default=None)
    _llama_cpp_client: Any | None = PrivateAttr(default=None)
    _client_errors: dict[str, str] = PrivateAttr(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def apply_defaults_from_env(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            data = {}

        ollama_base_url = str(
            data.get("ollama_base_url") or os.getenv("LLM_URL", "http://ollama-llm:11434")
        ).strip() or "http://ollama-llm:11434"
        llama_cpp_base_url = str(
            data.get("llama_cpp_base_url")
            or os.getenv("LLAMA_CPP_URL", "http://llama-cpp-backend:8080")
        ).strip() or "http://llama-cpp-backend:8080"
        api_key = str(data.get("api_key") or os.getenv("LLM_KEY", "")).strip()
        chat_model = str(data.get("chat_model") or os.getenv("LLM_MODEL", "")).strip()
        embedding_model = str(
            data.get("embedding_model") or os.getenv("LLM_EMBED", "")
        ).strip()
        default_provider = cls._normalize_provider(
            str(data.get("default_provider") or os.getenv("LLM_DEFAULT_PROVIDER", "ollama"))
        )

        return {
            **data,
            "ollama_base_url": ollama_base_url,
            "llama_cpp_base_url": llama_cpp_base_url,
            "api_key": api_key,
            "chat_model": chat_model,
            "embedding_model": embedding_model,
            "default_provider": default_provider,
        }

    @model_validator(mode="after")
    def initialize(self) -> "OpenAIClientService":
        if self.client_factory is None:
            self.client_factory = self._default_client_factory

        # Initialize both clients once so future services can reuse them.
        self.initialize_clients()
        return self

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"

    @classmethod
    def _normalize_provider(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_").replace(".", "_")
        if normalized in {"llama", "llama_cpp", "llama_cpp_backend"}:
            return "llama_cpp"
        if normalized == "ollama":
            return "ollama"
        return "ollama"

    @staticmethod
    def _default_client_factory(base_url: str, api_key: str) -> Any:
        from openai import OpenAI  # type: ignore[import-not-found]

        return OpenAI(base_url=base_url, api_key=api_key)

    def initialize_clients(self) -> None:
        self._client_errors = {}

        self._ollama_client = self._build_client("ollama")
        self._llama_cpp_client = self._build_client("llama_cpp")

    def _build_client(self, provider: str) -> Any | None:
        if self.client_factory is None:
            raise ValueError("client_factory must be configured")

        normalized_provider = self._normalize_provider(provider)
        base_url = self._provider_base_url(normalized_provider)
        api_key = self.api_key or "not-needed"

        try:
            return self.client_factory(base_url, api_key)
        except Exception as exc:
            self._client_errors[normalized_provider] = str(exc)
            return None

    def _provider_base_url(self, provider: str) -> str:
        if provider == "ollama":
            return self._normalize_base_url(self.ollama_base_url)
        if provider == "llama_cpp":
            return self._normalize_base_url(self.llama_cpp_base_url)
        raise ValueError(f"Unsupported provider: {provider}")

    def get_client(self, provider: str | None = None) -> Any:
        selected_provider = self._normalize_provider(provider or self.default_provider)

        if selected_provider == "ollama":
            if self._ollama_client is None:
                self._ollama_client = self._build_client("ollama")
            if self._ollama_client is None:
                error = self._client_errors.get("ollama", "Unknown client initialization error")
                raise RuntimeError(f"Failed to initialize Ollama OpenAI client: {error}")
            return self._ollama_client

        if self._llama_cpp_client is None:
            self._llama_cpp_client = self._build_client("llama_cpp")
        if self._llama_cpp_client is None:
            error = self._client_errors.get("llama_cpp", "Unknown client initialization error")
            raise RuntimeError(f"Failed to initialize llama.cpp OpenAI client: {error}")
        return self._llama_cpp_client

    def get_ollama_client(self) -> Any:
        return self.get_client("ollama")

    def get_llama_cpp_client(self) -> Any:
        return self.get_client("llama_cpp")

    def status_payload(self) -> dict[str, Any]:
        return {
            "default_provider": self.default_provider,
            "chat_model": self.chat_model or None,
            "embedding_model": self.embedding_model or None,
            "providers": {
                "ollama": {
                    "base_url": self._normalize_base_url(self.ollama_base_url),
                    "initialized": self._ollama_client is not None,
                    "error": self._client_errors.get("ollama"),
                },
                "llama_cpp": {
                    "base_url": self._normalize_base_url(self.llama_cpp_base_url),
                    "initialized": self._llama_cpp_client is not None,
                    "error": self._client_errors.get("llama_cpp"),
                },
            },
        }
