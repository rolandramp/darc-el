from __future__ import annotations

from pydantic import BaseModel


class DocumentUploadRequest(BaseModel):
    source: str | None = None
