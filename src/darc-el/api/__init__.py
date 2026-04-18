from __future__ import annotations

from fastapi import FastAPI

from api.routes import router


def create_default_download_status() -> dict[str, object | None]:
    return {
        "state": "idle",
        "updated_at": None,
        "library_id": None,
        "library_type": None,
        "output_file": None,
        "item_count": None,
        "message": "No downloads have been requested yet.",
    }


def create_default_upload_status() -> dict[str, object | None]:
    return {
        "state": "idle",
        "updated_at": None,
        "item_count": None,
        "message": "No uploads have been requested yet.",
    }


def initialize_app_state(app: FastAPI) -> None:
    app.state.download_status = create_default_download_status()
    app.state.upload_status = create_default_upload_status()
