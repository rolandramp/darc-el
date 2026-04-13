import os
import sys
import importlib.util
from pathlib import Path

from dotenv import load_dotenv


def _load_zotero_download_service_class():
    service_path = Path(__file__).resolve().parent / "darc-el" / "service" / "download_service.py"
    spec = importlib.util.spec_from_file_location("download_service", service_path)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load download service module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ZoteroDownloadService


ZoteroDownloadService = _load_zotero_download_service_class()

def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Missing required environment variable: {name}")
        sys.exit(1)
    return value


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=True)
    library_id = require_env("ZOTERO_LIBRARY_ID")
    api_key = require_env("ZOTERO_API_KEY")
    # Default to group access for this downloader.
    library_type = os.getenv("ZOTERO_LIBRARY_TYPE", "group").strip() or "group"
    output_file = os.getenv("ZOTERO_OUTPUT_FILE", "zotero_group_items.json").strip() or "zotero_group_items.json"

    download_service = ZoteroDownloadService(
        library_id=library_id,
        api_key=api_key,
        library_type=library_type,
    )
    items = download_service.download_items()

    print(f"Connected to Zotero {library_type} library {library_id}")
    print(f"Downloaded {len(items)} item(s)")

    download_service.save_items_to_file(items, output_file)

    print(f"Saved all items to {output_file}")

    for item in items:
        data = item.get("data", {})
        item_type = data.get("itemType", "unknown")
        key = data.get("key", "unknown")
        title = data.get("title", "(no title)")
        print(f"- {item_type} | {key} | {title}")


if __name__ == "__main__":
    main()
