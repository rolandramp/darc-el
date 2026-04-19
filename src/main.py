from __future__ import annotations

import argparse
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import ValidationError

PACKAGE_ROOT = Path(__file__).resolve().parent / "darc-el"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from service.llm_client_service import LLMRegistryFileConfig


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)
    yield


app = FastAPI(title="DARC-EL Service API", lifespan=lifespan)


def configure_app(app: FastAPI) -> None:
    from api import (  # type: ignore[import-not-found]
        router,
    )

    app.include_router(router)


configure_app(app)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the DARC-EL service API")
    parser.add_argument(
        "--llm-config-path",
        required=True,
        help="Path to the llm_models.yaml file",
    )
    return parser


def load_llm_registry_config(config_path: str) -> LLMRegistryFileConfig:
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


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Missing required environment variable: {name}")
        sys.exit(1)
    return value


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    from api import initialize_app_state  # type: ignore[import-not-found]

    registry_config = load_llm_registry_config(args.llm_config_path)

    initialize_app_state(app, registry_config=registry_config)

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
