import os
import sys
import json
from pathlib import Path

from pyzotero import zotero

from dotenv import load_dotenv

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

    client = zotero.Zotero(library_id, library_type, api_key)
    items = client.everything(client.items())

    print(f"Connected to Zotero {library_type} library {library_id}")
    print(f"Downloaded {len(items)} item(s)")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"Saved all items to {output_file}")

    for item in items:
        data = item.get("data", {})
        item_type = data.get("itemType", "unknown")
        key = data.get("key", "unknown")
        title = data.get("title", "(no title)")
        print(f"- {item_type} | {key} | {title}")


if __name__ == "__main__":
    main()
