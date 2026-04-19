from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.document_ingestion import DocumentIngestionRecord
from core.download_request import DownloadRequest
from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile
from service.document_ingestion_service import (  # type: ignore[import-not-found]
    DocumentIngestionService,
    UnsupportedDocumentTypeError,
)
from service.download_service import ZoteroDownloadService
from service.neo4j_document_service import Neo4jDocumentService

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_download_status(request: Request, **updates: object | None) -> None:
    request.app.state.download_status.update(updates)


def _set_upload_status(request: Request, **updates: object | None) -> None:
    request.app.state.upload_status.update(updates)


@router.get(
    "/health",
    summary="Health check",
    description="Returns a lightweight service health indicator.",
    response_description="Service health status.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/status",
    summary="Get download status",
    description="Returns the latest state for the Zotero download workflow.",
    response_description="Current download status payload.",
)
def status(request: Request) -> dict[str, object | None]:
    return dict(request.app.state.download_status)


@router.post(
    "/download",
    summary="Download Zotero items",
    description=(
        "Downloads items from a Zotero library and persists the raw item data to disk. "
        "When no request body is supplied, server-side defaults or environment values are used."
    ),
    response_description="Download result including item count, items, and output file path.",
    responses={
        400: {"description": "Invalid or missing download configuration."},
        502: {"description": "Upstream Zotero download failed."},
    },
)
def download(
    request: Request,
    download_request: DownloadRequest | None = Body(
        default=None,
        description="Optional Zotero credentials and output settings.",
    ),
) -> dict[str, object]:
    try:
        download_service, output_file = ZoteroDownloadService.from_download_request(
            download_request
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    library_id = download_service.library_id
    library_type = download_service.library_type

    _set_download_status(
        request,
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
            request,
            state="failed",
            updated_at=_now_iso(),
            message=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"Download failed: {exc}") from exc

    item_count = len(items)
    _set_download_status(
        request,
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


@router.get(
    "/upload/status",
    summary="Get upload status",
    description="Returns the latest state for document upload and ingestion.",
    response_description="Current upload status payload.",
)
def upload_status(request: Request) -> dict[str, object | None]:
    return dict(request.app.state.upload_status)


@router.get(
    "/llm/status",
    summary="Get LLM provider status",
    description="Returns runtime status and configuration visibility for enabled LLM providers.",
    response_description="LLM client status payload.",
)
def llm_status(request: Request) -> dict[str, Any]:
    llm_client_service = request.app.state.llm_client_service
    return llm_client_service.status_payload()


@router.post(
    "/upload",
    summary="Upload and ingest documents",
    description=(
        "Accepts one or more files, parses document text into chunks, and ingests the "
        "resulting records into Neo4j."
    ),
    response_description="Upload and ingestion results per file plus Neo4j ingestion summary.",
    responses={
        400: {"description": "No files were supplied."},
        415: {"description": "Unsupported document content type."},
        502: {"description": "Document parsing or Neo4j ingestion failed."},
    },
)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(..., description="One or more files to parse and ingest."),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    ingestion_service = DocumentIngestionService()

    _set_upload_status(
        request,
        state="running",
        updated_at=_now_iso(),
        item_count=len(files),
        message="Upload in progress.",
    )

    records: list[DocumentIngestionRecord] = []
    file_results: list[dict[str, Any]] = []
    for upload_file in files:
        try:
            data = await upload_file.read()
            record = ingestion_service.ingest_upload(
                upload_file.filename or "uploaded-file",
                upload_file.content_type,
                data,
            )
            records.append(record)
            file_results.append(
                {
                    "file_name": record.file_name,
                    "status": "parsed",
                    "source_type": record.source_type,
                    "chunk_count": len(record.chunks),
                }
            )
        except UnsupportedDocumentTypeError as exc:
            _set_upload_status(request, state="failed", updated_at=_now_iso(), message=str(exc))
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        except Exception as exc:
            _set_upload_status(request, state="failed", updated_at=_now_iso(), message=str(exc))
            raise HTTPException(status_code=502, detail=f"Upload parsing failed: {exc}") from exc

    try:
        neo4j_service = Neo4jDocumentService()
        neo4j_results = neo4j_service.ingest_documents(records)
    except Exception as exc:
        _set_upload_status(request, state="failed", updated_at=_now_iso(), message=str(exc))
        raise HTTPException(status_code=502, detail=f"Neo4j ingestion failed: {exc}") from exc

    _set_upload_status(
        request,
        state="completed",
        updated_at=_now_iso(),
        item_count=len(records),
        message=f"Uploaded {len(records)} file(s).",
    )

    return {
        "status": "completed",
        "file_count": len(records),
        "files": file_results,
        "neo4j": neo4j_results,
    }
