"""Backward-compatible alias for the canonical document service."""

from service.document_service import DocumentService, UnsupportedDocumentTypeError


class DocumentIngestionService(DocumentService):
    pass
