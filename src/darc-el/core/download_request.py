from pydantic import BaseModel


class DownloadRequest(BaseModel):
    library_id: str | None = None
    api_key: str | None = None
    library_type: str | None = None
    output_file: str | None = None