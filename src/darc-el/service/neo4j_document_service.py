from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, model_validator

from core.document_ingestion import DocumentIngestionRecord


class Neo4jDocumentService(BaseModel):
    uri: str = "bolt://neo4j-kg:7687"
    user: str = "neo4j"
    password: str = ""

    @model_validator(mode="before")
    @classmethod
    def apply_defaults_from_env(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        uri = str(data.get("uri") or os.getenv("NEO4J_URI", "bolt://neo4j-kg:7687")).strip() or "bolt://neo4j-kg:7687"
        user = str(data.get("user") or os.getenv("NEO4J_USER", "neo4j")).strip() or "neo4j"
        password = str(data.get("password") or os.getenv("NEO4J_PASS", "")).strip()

        return {
            "uri": uri,
            "user": user,
            "password": password,
        }

    @model_validator(mode="after")
    def validate_password(self) -> "Neo4jDocumentService":
        if not self.password:
            raise ValueError("Missing Neo4j password")
        return self

    def ingest_documents(self, records: list[DocumentIngestionRecord]) -> list[dict[str, Any]]:
        if not records:
            return []

        driver = self._create_driver()
        try:
            with driver.session() as session:
                return [session.execute_write(self._write_record, record) for record in records]
        finally:
            driver.close()

    def _create_driver(self):
        from neo4j import GraphDatabase

        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def _write_record(self, tx, record: DocumentIngestionRecord) -> dict[str, Any]:
        metadata_properties = self._sanitize_properties(record.metadata)
        result = tx.run(
            """
            MERGE (d:Document {file_name: $file_name, source_type: $source_type})
            SET d.content_type = $content_type,
                d.parser_name = $parser_name,
                d.text = $text,
                d.updated_at = datetime()
            WITH d
            CREATE (m:DocumentMetadata)
            SET m += $metadata
            CREATE (d)-[:HAS_METADATA]->(m)
            WITH d
            UNWIND $chunks AS chunk
              CREATE (c:DocumentChunk)
              SET c.index = chunk.index,
                  c.text = chunk.text
              CREATE (d)-[:HAS_CHUNK]->(c)
            RETURN d.file_name AS file_name, d.source_type AS source_type, count(*) AS chunk_link_count
            """,
            file_name=record.file_name,
            source_type=record.source_type,
            content_type=record.content_type,
            parser_name=record.parser_name,
            text=record.text,
            metadata=metadata_properties,
            chunks=[{"index": chunk.index, "text": chunk.text} for chunk in record.chunks],
        )
        summary = result.single() if hasattr(result, "single") else None
        return {
            "file_name": record.file_name,
            "source_type": record.source_type,
            "status": "completed",
            "chunk_count": len(record.chunks),
            "neo4j": dict(summary) if summary is not None else {},
        }

    def _sanitize_properties(self, metadata: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            sanitized[str(key)] = self._sanitize_value(value)
        return sanitized

    def _sanitize_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            if all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
                return value
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
