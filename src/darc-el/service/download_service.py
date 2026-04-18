import json
import os
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ZoteroDownloadService(BaseModel):
    """Download and persist items from a Zotero library."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    library_id: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    library_type: str = "group"
    client_factory: Optional[Callable[[str, str, str], Any]] = None

    @model_validator(mode="after")
    def set_default_client_factory(self):
        if self.client_factory is None:
            self.client_factory = self._default_client_factory
        return self

    @staticmethod
    def _default_client_factory(library_id: str, library_type: str, api_key: str):
        from pyzotero import zotero

        return zotero.Zotero(library_id, library_type, api_key)

    def download_items(self) -> list[dict]:
        if self.client_factory is None:
            raise ValueError("client_factory must be configured")
        client = self.client_factory(self.library_id, self.library_type, self.api_key)
        return client.everything(client.items())

    @classmethod
    def from_download_request(
        cls, download_request: Any | None = None
    ) -> tuple["ZoteroDownloadService", str]:
        request_data: dict[str, Any] = {}
        if download_request is not None:
            if hasattr(download_request, "model_dump"):
                request_data = download_request.model_dump(exclude_none=True)
            elif isinstance(download_request, dict):
                request_data = download_request

        library_id = str(
            request_data.get("library_id") or os.getenv("ZOTERO_LIBRARY_ID", "")
        ).strip()
        api_key = str(
            request_data.get("api_key") or os.getenv("ZOTERO_API_KEY", "")
        ).strip()
        library_type = str(
            request_data.get("library_type")
            or os.getenv("ZOTERO_LIBRARY_TYPE", "group")
        ).strip() or "group"
        output_file = str(
            request_data.get("output_file")
            or os.getenv("ZOTERO_OUTPUT_FILE", "zotero_group_items.json")
        ).strip() or "zotero_group_items.json"

        if not library_id:
            raise ValueError("Missing Zotero library ID")
        if not api_key:
            raise ValueError("Missing Zotero API key")

        service = cls(
            library_id=library_id,
            api_key=api_key,
            library_type=library_type,
        )
        return service, output_file

    def save_items_to_file(self, items: list[dict], output_file: str) -> None:
        with open(output_file, "w", encoding="utf-8") as file_handle:
            json.dump(items, file_handle, ensure_ascii=False, indent=2)
