from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    field_validator,
    model_validator,
)

ProviderClientFactory = Callable[[str, str], Any]
SUPPORTED_PROVIDERS = {"ollama", "llama_cpp"}
DEFAULT_LLM_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "llm_models.yaml"


def normalize_provider(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(".", "_")
    if normalized in {"llama", "llama_cpp", "llama_cpp_backend"}:
        return "llama_cpp"
    if normalized == "ollama":
        return "ollama"
    return ""


class LLMModelDefinition(BaseModel):
    provider: str
    base_url: str

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, value: Any) -> str:
        provider = normalize_provider(str(value or ""))
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider: {value}")
        return provider

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("base_url must not be empty")
        return normalized


class LLMRegistryFileConfig(BaseModel):
    default_provider: str = "ollama"
    default_model: str
    default_embedding_model: str
    provider_defaults: dict[str, str] = Field(default_factory=dict)
    models: dict[str, LLMModelDefinition]

    @field_validator("default_provider", mode="before")
    @classmethod
    def validate_default_provider(cls, value: Any) -> str:
        provider = normalize_provider(str(value or "ollama"))
        if provider not in SUPPORTED_PROVIDERS:
            return "ollama"
        return provider

    @model_validator(mode="after")
    def validate_references(self) -> "LLMRegistryFileConfig":
        if self.default_model not in self.models:
            raise ValueError(
                f"default_model '{self.default_model}' is not present in models registry"
            )
        if self.default_embedding_model not in self.models:
            raise ValueError(
                f"default_embedding_model '{self.default_embedding_model}' is not present in models registry"
            )

        normalized_defaults: dict[str, str] = {}
        for raw_provider, model_name in self.provider_defaults.items():
            provider = normalize_provider(raw_provider)
            if provider not in SUPPORTED_PROVIDERS:
                raise ValueError(f"Unsupported provider in provider_defaults: {raw_provider}")
            if model_name not in self.models:
                raise ValueError(
                    f"provider_defaults references unknown model '{model_name}' for provider '{provider}'"
                )
            normalized_defaults[provider] = model_name

        self.provider_defaults = normalized_defaults
        return self


class OpenAIClientService(BaseModel):
    """Create and hold OpenAI-compatible clients in a model-keyed registry."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_config_path: str = Field(default="")
    api_key: str = Field(default="")
    chat_model: str = Field(default="")
    embedding_model: str = Field(default="")
    default_provider: str = Field(default="")
    default_model: str = Field(default="")
    client_factory: ProviderClientFactory | None = None

    _registry_config: LLMRegistryFileConfig | None = PrivateAttr(default=None)
    _model_definitions: dict[str, LLMModelDefinition] = PrivateAttr(default_factory=dict)
    _model_client_registry: dict[str, Any | None] = PrivateAttr(default_factory=dict)
    _model_errors: dict[str, str] = PrivateAttr(default_factory=dict)
    _provider_default_models: dict[str, str] = PrivateAttr(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def apply_defaults_from_env(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            data = {}

        llm_config_path = str(
            data.get("llm_config_path") or os.getenv("LLM_CONFIG_PATH", str(DEFAULT_LLM_CONFIG_PATH))
        ).strip() or str(DEFAULT_LLM_CONFIG_PATH)
        api_key = str(data.get("api_key") or os.getenv("LLM_KEY", "")).strip()
        chat_model = str(data.get("chat_model", "")).strip()
        embedding_model = str(data.get("embedding_model", "")).strip()
        default_provider = str(data.get("default_provider", "")).strip()
        default_model = str(data.get("default_model", "")).strip()

        return {
            **data,
            "llm_config_path": llm_config_path,
            "api_key": api_key,
            "chat_model": chat_model,
            "embedding_model": embedding_model,
            "default_provider": default_provider,
            "default_model": default_model,
        }

    @model_validator(mode="after")
    def initialize(self) -> "OpenAIClientService":
        if self.client_factory is None:
            self.client_factory = self._default_client_factory

        registry_config = self._load_registry_config(self.llm_config_path)
        self._registry_config = registry_config
        self._model_definitions = dict(registry_config.models)
        self._provider_default_models = self._resolve_provider_defaults(registry_config)

        if not self.default_model:
            self.default_model = registry_config.default_model
        if not self.chat_model:
            self.chat_model = self.default_model
        if not self.embedding_model:
            self.embedding_model = registry_config.default_embedding_model

        requested_provider = normalize_provider(self.default_provider)
        if requested_provider and requested_provider in SUPPORTED_PROVIDERS:
            self.default_provider = requested_provider
        else:
            self.default_provider = registry_config.default_provider

        # Initialize all configured model clients once so future services can reuse them.
        self.initialize_clients()
        return self

    @staticmethod
    def _load_registry_config(config_path: str) -> LLMRegistryFileConfig:
        path = Path(config_path)
        if not path.exists():
            raise ValueError(f"LLM config file not found: {path}")

        try:
            with path.open("r", encoding="utf-8") as config_file:
                raw_config = yaml.safe_load(config_file) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML at {path}: {exc}") from exc

        if not isinstance(raw_config, dict):
            raise ValueError(f"LLM config at {path} must be a YAML object")

        try:
            return LLMRegistryFileConfig.model_validate(raw_config)
        except ValidationError as exc:
            raise ValueError(f"Invalid LLM config at {path}: {exc}") from exc

    def _resolve_provider_defaults(self, registry_config: LLMRegistryFileConfig) -> dict[str, str]:
        defaults = dict(registry_config.provider_defaults)

        for model_name, model_definition in registry_config.models.items():
            defaults.setdefault(model_definition.provider, model_name)

        defaults.setdefault(registry_config.default_provider, registry_config.default_model)
        return defaults

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"

    @staticmethod
    def _default_client_factory(base_url: str, api_key: str) -> Any:
        from openai import OpenAI  # type: ignore[import-not-found]

        return OpenAI(base_url=base_url, api_key=api_key)

    def initialize_clients(self) -> None:
        self._model_errors = {}
        self._model_client_registry = {}

        for model_name in self._model_definitions:
            self._model_client_registry[model_name] = self._build_client(model_name)

    def _build_client(self, model_name: str) -> Any | None:
        if self.client_factory is None:
            raise ValueError("client_factory must be configured")

        model_definition = self._model_definitions[model_name]
        base_url = self._normalize_base_url(model_definition.base_url)
        api_key = self.api_key or "not-needed"

        try:
            return self.client_factory(base_url, api_key)
        except Exception as exc:
            self._model_errors[model_name] = str(exc)
            return None

    def _default_model_for_provider(self, provider: str) -> str:
        model_name = self._provider_default_models.get(provider)
        if model_name:
            return model_name

        for candidate_model, model_definition in self._model_definitions.items():
            if model_definition.provider == provider:
                return candidate_model

        raise ValueError(f"No model configured for provider: {provider}")

    def get_client(self, model_name: str | None = None, provider: str | None = None) -> Any:
        selected_model = (model_name or "").strip()
        if not selected_model:
            if provider:
                normalized_provider = normalize_provider(provider)
                if normalized_provider not in SUPPORTED_PROVIDERS:
                    raise ValueError(f"Unsupported provider: {provider}")
                selected_model = self._default_model_for_provider(normalized_provider)
            else:
                selected_model = self.default_model

        if selected_model not in self._model_definitions:
            raise ValueError(f"Unknown model: {selected_model}")

        selected_client = self._model_client_registry.get(selected_model)
        if selected_client is None:
            selected_client = self._build_client(selected_model)
            self._model_client_registry[selected_model] = selected_client

        if selected_client is None:
            error = self._model_errors.get(selected_model, "Unknown client initialization error")
            raise RuntimeError(f"Failed to initialize OpenAI client for model '{selected_model}': {error}")
        return selected_client

    def get_ollama_client(self) -> Any:
        return self.get_client(provider="ollama")

    def get_llama_cpp_client(self) -> Any:
        return self.get_client(provider="llama_cpp")

    def status_payload(self) -> dict[str, Any]:
        models_payload: dict[str, dict[str, Any]] = {}
        for model_name, model_definition in self._model_definitions.items():
            models_payload[model_name] = {
                "provider": model_definition.provider,
                "base_url": self._normalize_base_url(model_definition.base_url),
                "initialized": self._model_client_registry.get(model_name) is not None,
                "error": self._model_errors.get(model_name),
            }

        providers_payload: dict[str, dict[str, Any]] = {}
        for provider in sorted(SUPPORTED_PROVIDERS):
            provider_model = self._provider_default_models.get(provider)
            provider_definition = (
                self._model_definitions.get(provider_model) if provider_model is not None else None
            )
            providers_payload[provider] = {
                "default_model": provider_model,
                "base_url": (
                    self._normalize_base_url(provider_definition.base_url)
                    if provider_definition is not None
                    else None
                ),
                "initialized": (
                    self._model_client_registry.get(provider_model) is not None
                    if provider_model is not None
                    else False
                ),
                "error": self._model_errors.get(provider_model or ""),
            }

        return {
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "chat_model": self.chat_model or None,
            "embedding_model": self.embedding_model or None,
            "llm_config_path": self.llm_config_path,
            "providers": providers_payload,
            "models": models_payload,
        }
