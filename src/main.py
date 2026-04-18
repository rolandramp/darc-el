from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent / "darc-el"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from core.download_request import DownloadRequest  # type: ignore[import-not-found]
from service.download_service import ZoteroDownloadService  # type: ignore[import-not-found]


def _create_default_download_status() -> dict[str, object | None]:
    return {
        "state": "idle",
        "updated_at": None,
        "library_id": None,
        "library_type": None,
        "output_file": None,
        "item_count": None,
        "message": "No downloads have been requested yet.",
    }


router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)
    yield


app = FastAPI(title="DARC-EL Zotero Download API", lifespan=lifespan)
app.state.download_status = _create_default_download_status()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_download_status(**updates: object | None) -> None:
    app.state.download_status.update(updates)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status")
def status() -> dict[str, object | None]:
    return dict(app.state.download_status)


@router.post("/download")
def download(download_request: DownloadRequest | None = None) -> dict[str, object]:
    try:
        download_service, output_file = ZoteroDownloadService.from_download_request(
            download_request
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    library_id = download_service.library_id
    library_type = download_service.library_type

    _set_download_status(
        state="running",
        updated_at=_now_iso(),
        library_id=library_id,
        library_type=library_type,
        output_file=output_file,
        item_count=None,
        message="Download in progress.",
    )

    try:
        items = download_service.download_items()
        download_service.save_items_to_file(items, output_file)
    except Exception as exc:  # pragma: no cover - exercised through API tests
        _set_download_status(
            state="failed",
            updated_at=_now_iso(),
            message=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"Download failed: {exc}") from exc

    item_count = len(items)
    _set_download_status(
        state="completed",
        updated_at=_now_iso(),
        item_count=item_count,
        message=f"Downloaded {item_count} item(s).",
    )

    return {
        "status": "completed",
        "item_count": item_count,
        "items": items,
        "output_file": output_file,
    }


app.include_router(router)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Missing required environment variable: {name}")
        sys.exit(1)
    return value


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
