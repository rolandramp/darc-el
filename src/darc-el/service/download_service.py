import json
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

    def save_items_to_file(self, items: list[dict], output_file: str) -> None:
        with open(output_file, "w", encoding="utf-8") as file_handle:
            json.dump(items, file_handle, ensure_ascii=False, indent=2)
