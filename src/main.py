from __future__ import annotations

import argparse
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

PACKAGE_ROOT = Path(__file__).resolve().parent / "darc-el"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


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

    initialize_app_state(app, llm_config_path=args.llm_config_path)

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
