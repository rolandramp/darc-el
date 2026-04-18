from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    index: int
    text: str


class DocumentIngestionRecord(BaseModel):
    file_name: str
    content_type: str
    source_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    text: str = ""
    chunks: list[DocumentChunk] = Field(default_factory=list)
    parser_name: str = ""

    @property
    def stem(self) -> str:
        return Path(self.file_name).stem
