import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from core.document_ingestion import DocumentChunk, DocumentIngestionRecord
from pydantic import ValidationError
from service.document_service import (
    DocumentService,
    UnsupportedDocumentTypeError,
)
from service.download_service import ZoteroDownloadService
from service.llm_client_service import LLMRegistryFileConfig, OpenAIClientService
from service.neo4j_document_service import Neo4jDocumentService

import main


class FakeZoteroClient:
    def __init__(self, items_payload):
        self._items_payload = items_payload

    def items(self):
        return ["raw-items"]

    def everything(self, raw_items):
        return self._items_payload if raw_items == ["raw-items"] else []


class DownloadServiceTests(unittest.TestCase):
    def test_download_items_uses_client_factory(self):
        payload = [{"data": {"title": "A"}}]

        def client_factory(library_id, library_type, api_key):
            self.assertEqual(library_id, "lib-id")
            self.assertEqual(library_type, "group")
            self.assertEqual(api_key, "api-key")
            return FakeZoteroClient(payload)

        service = ZoteroDownloadService(
            library_id="lib-id",
            api_key="api-key",
            library_type="group",
            client_factory=client_factory,
        )

        items = service.download_items()
        self.assertEqual(items, payload)

    def test_save_items_to_file_writes_json(self):
        items = [{"data": {"title": "Paper"}}]
        service = ZoteroDownloadService(
            library_id="lib-id",
            api_key="api-key",
            library_type="group",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "items.json"
            service.save_items_to_file(items, str(output_file))

            self.assertTrue(output_file.exists())
            written = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(written, items)

    def test_document_ingestion_service_detects_pdf_and_chunks_text(self):
        service = DocumentService()

        with patch.object(service, "_parse_pdf", return_value=({"page_count": 1}, "Hello world", "pypdf")) as parse_pdf_mock:
            record = service.ingest_upload("paper.pdf", "application/pdf", b"pdf-bytes")

        parse_pdf_mock.assert_called_once_with(b"pdf-bytes")
        self.assertEqual(record.source_type, "pdf")
        self.assertEqual(record.metadata["page_count"], 1)
        self.assertEqual(record.chunks[0].text, "Hello world")

    def test_document_ingestion_service_rejects_unsupported_type(self):
        service = DocumentService()

        with self.assertRaises(UnsupportedDocumentTypeError):
            service.ingest_upload("archive.zip", "application/zip", b"zip")

    def test_document_ingestion_service_chunks_long_text(self):
        service = DocumentService()
        chunks = service._chunk_text("a" * 2500, chunk_size=1000, overlap=100)

        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0].index, 0)
        self.assertTrue(all(isinstance(chunk, DocumentChunk) for chunk in chunks))

    def test_neo4j_document_service_uses_driver_and_writes_each_record(self):
        record = DocumentIngestionRecord(
            file_name="paper.pdf",
            content_type="application/pdf",
            source_type="pdf",
            metadata={"page_count": 1},
            text="Hello",
            chunks=[DocumentChunk(index=0, text="Hello")],
            parser_name="pypdf",
        )

        fake_result = type("FakeResult", (), {"single": lambda self: {"file_name": "paper.pdf"}})()
        fake_tx = type("FakeTx", (), {"run": lambda self, *args, **kwargs: fake_result})()
        fake_session = type("FakeSession", (), {"__enter__": lambda self: self, "__exit__": lambda self, exc_type, exc, tb: False, "execute_write": lambda self, func, item: func(fake_tx, item)})()
        fake_driver = type("FakeDriver", (), {"session": lambda self: fake_session, "close": lambda self: None})()

        service = Neo4jDocumentService(uri="bolt://example:7687", user="neo4j", password="secret")
        with patch.object(service, "_create_driver", return_value=fake_driver):
            results = service.ingest_documents([record])

        self.assertEqual(results[0]["file_name"], "paper.pdf")
        self.assertEqual(results[0]["status"], "completed")


class PydanticValidationTests(unittest.TestCase):
    def _write_llm_config(self, directory: str) -> str:
        config_path = Path(directory) / "llm_models.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "default_provider: llama.cpp",
                    'default_model: "ministral-3:3b"',
                    'default_embedding_model: "nomic-embed-text"',
                    "provider_defaults:",
                    '  ollama: "ministral-3:3b"',
                    '  llama_cpp: "mistralai/Ministral-3-3B-Instruct-2512-GGUF:Q4_K_M"',
                    '  openrouter: "openrouter/auto"',
                    "models:",
                    '  "ministral-3:3b":',
                    "    provider: ollama",
                    "    base_url: http://ollama:11434",
                    '  "nomic-embed-text":',
                    "    provider: ollama",
                    "    base_url: http://ollama:11434",
                    '  "mistralai/Ministral-3-3B-Instruct-2512-GGUF:Q4_K_M":',
                    "    provider: llama.cpp",
                    "    base_url: http://llama-cpp:8080",
                    '  "openrouter/auto":',
                    "    provider: openrouter",
                    "    base_url: https://openrouter.ai/api/v1",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return str(config_path)

    def test_document_chunk_coerces_index_type(self):
        chunk = DocumentChunk.model_validate({"index": "7", "text": "chunk text"})
        self.assertEqual(chunk.index, 7)
        self.assertEqual(chunk.text, "chunk text")

    def test_document_ingestion_record_applies_defaults(self):
        record = DocumentIngestionRecord(
            file_name="paper.pdf",
            content_type="application/pdf",
            source_type="pdf",
        )

        self.assertEqual(record.metadata, {})
        self.assertEqual(record.text, "")
        self.assertEqual(record.chunks, [])
        self.assertEqual(record.parser_name, "")

    def test_document_ingestion_record_requires_fields(self):
        with self.assertRaises(ValidationError):
            DocumentIngestionRecord.model_validate(
                {"content_type": "application/pdf", "source_type": "pdf"}
            )

    def test_neo4j_service_uses_env_defaults(self):
        with patch.dict(
            "os.environ",
            {
                "NEO4J_URI": " bolt://example:7687 ",
                "NEO4J_USER": " neo4j-user ",
                "NEO4J_PASS": " secret ",
            },
            clear=True,
        ):
            service = Neo4jDocumentService()

        self.assertEqual(service.uri, "bolt://example:7687")
        self.assertEqual(service.user, "neo4j-user")
        self.assertEqual(service.password, "secret")

    def test_neo4j_service_requires_password(self):
        with patch.dict(
            "os.environ",
            {
                "NEO4J_URI": "bolt://example:7687",
                "NEO4J_USER": "neo4j-user",
            },
            clear=True,
        ):
            with self.assertRaises(ValidationError) as exc:
                Neo4jDocumentService()

        self.assertIn("Missing Neo4j password", str(exc.exception))

    def test_llm_client_service_uses_yaml_registry(self):
        created_clients: list[tuple[str, str]] = []

        def fake_client_factory(base_url: str, api_key: str):
            created_clients.append((base_url, api_key))
            return {"base_url": base_url, "api_key": api_key}

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_llm_config(temp_dir)
            registry_config = LLMRegistryFileConfig.model_validate(
                yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
            )
            service = OpenAIClientService(
                registry_config=registry_config,
                api_key=" test-key ",
                client_factory=fake_client_factory,
            )

        self.assertEqual(service.default_provider, "llama_cpp")
        self.assertEqual(service.default_model, "ministral-3:3b")
        self.assertEqual(service.chat_model, "ministral-3:3b")
        self.assertEqual(service.embedding_model, "nomic-embed-text")
        self.assertEqual(
            created_clients,
            [
                ("http://ollama:11434/v1", "test-key"),
                ("http://ollama:11434/v1", "test-key"),
                ("http://llama-cpp:8080/v1", "test-key"),
                ("https://openrouter.ai/api/v1", "test-key"),
            ],
        )
        self.assertEqual(
            service.get_client(model_name="ministral-3:3b"),
            {"base_url": "http://ollama:11434/v1", "api_key": "test-key"},
        )
        self.assertEqual(
            service.get_llama_cpp_client(),
            {"base_url": "http://llama-cpp:8080/v1", "api_key": "test-key"},
        )
        self.assertEqual(
            service.get_openrouter_client(),
            {"base_url": "https://openrouter.ai/api/v1", "api_key": "test-key"},
        )
        status_payload = service.status_payload()
        self.assertIn("models", status_payload)
        self.assertIn("ministral-3:3b", status_payload["models"])
        self.assertIn("openrouter", status_payload["providers"])

    def test_llm_client_service_falls_back_to_ollama_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_llm_config(temp_dir)
            registry_config = LLMRegistryFileConfig.model_validate(
                yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
            )
            service = OpenAIClientService(
                registry_config=registry_config,
                default_provider="unknown",
                client_factory=lambda base_url, api_key: {
                    "base_url": base_url,
                    "api_key": api_key,
                },
            )

        self.assertEqual(service.default_provider, "llama_cpp")
        selected_client = service.get_client()
        self.assertEqual(selected_client["base_url"], "http://ollama:11434/v1")

    def test_llm_client_service_raises_for_missing_yaml(self):
        with self.assertRaises(ValueError) as exc:
            main.load_llm_registry_config("C:/missing/llm_models.yaml")

        self.assertIn("LLM config file not found", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
