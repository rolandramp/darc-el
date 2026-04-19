import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

api_routes = importlib.import_module("api.routes")
api_module = importlib.import_module("api")
document_ingestion = importlib.import_module("core.document_ingestion")
DocumentChunk = document_ingestion.DocumentChunk
DocumentIngestionRecord = document_ingestion.DocumentIngestionRecord
main = importlib.import_module("main")

LLM_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "llm_models.yaml"


class MainOrchestrationTests(unittest.TestCase):
    def setUp(self):
        registry_config = main.load_llm_registry_config(str(LLM_CONFIG_PATH))
        api_module.initialize_app_state(main.app, registry_config)

    @patch("main.load_dotenv")
    def test_health_endpoint_returns_ok(self, load_dotenv_mock):
        with TestClient(main.app) as client:
            response = client.get("/health")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("main.load_dotenv")
    def test_status_endpoint_reports_idle_before_download(self, load_dotenv_mock):
        with TestClient(main.app) as client:
            response = client.get("/status")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], "idle")
        self.assertIsNone(payload["item_count"])

    @patch("main.load_dotenv")
    def test_download_endpoint_uses_service_and_updates_status(
        self, load_dotenv_mock
    ):
        service_instance = MagicMock()
        service_instance.library_id = "library-id"
        service_instance.library_type = "group"
        service_instance.download_items.return_value = [
            {"data": {"itemType": "book", "key": "ABC", "title": "Demo"}}
        ]

        with patch.object(
            api_routes.ZoteroDownloadService,
            "from_download_request",
            return_value=(service_instance, "output.json"),
        ) as from_request_mock:
            with TestClient(main.app) as client:
                response = client.post("/download")

        load_dotenv_mock.assert_called_once()
        from_request_mock.assert_called_once_with(None)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["item_count"], 1)
        self.assertEqual(payload["items"], service_instance.download_items.return_value)
        service_instance.download_items.assert_called_once_with()
        service_instance.save_items_to_file.assert_called_once_with(
            service_instance.download_items.return_value, "output.json"
        )

        status_response = None
        with TestClient(main.app) as client:
            status_response = client.get("/status")

        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["state"], "completed")
        self.assertEqual(status_payload["item_count"], 1)

    @patch("main.load_dotenv")
    def test_download_endpoint_rejects_missing_credentials(self, load_dotenv_mock):
        with patch.object(
            api_routes.ZoteroDownloadService,
            "from_download_request",
            side_effect=ValueError("Missing Zotero library ID"),
        ):
            with TestClient(main.app) as client:
                response = client.post("/download")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Missing Zotero library ID")

    @patch("main.load_dotenv")
    def test_upload_endpoint_parses_files_and_writes_to_neo4j(self, load_dotenv_mock):
        record_one = DocumentIngestionRecord(
            file_name="paper-a.pdf",
            content_type="application/pdf",
            source_type="pdf",
            metadata={"page_count": 1},
            text="Alpha",
            chunks=[DocumentChunk(index=0, text="Alpha")],
            parser_name="pypdf",
        )
        record_two = DocumentIngestionRecord(
            file_name="notes.txt",
            content_type="text/plain",
            source_type="text",
            metadata={"encoding": "utf-8"},
            text="Beta",
            chunks=[DocumentChunk(index=0, text="Beta")],
            parser_name="utf-8-text",
        )

        document_service = MagicMock()
        document_service.ingest_upload.side_effect = [record_one, record_two]
        document_service.ingest_records.return_value = [
            {"file_name": "paper-a.pdf", "status": "completed"},
            {"file_name": "notes.txt", "status": "completed"},
        ]

        with patch.object(api_routes, "DocumentService", return_value=document_service):
            with TestClient(main.app) as client:
                response = client.post(
                    "/upload",
                    files=[
                        ("files", ("paper-a.pdf", b"pdf-bytes", "application/pdf")),
                        ("files", ("notes.txt", b"Beta", "text/plain")),
                    ],
                )

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["file_count"], 2)
        self.assertEqual(payload["parsed_count"], 2)
        self.assertEqual(payload["failed_count"], 0)
        self.assertEqual(len(payload["files"]), 2)
        document_service.ingest_upload.assert_any_call("paper-a.pdf", "application/pdf", b"pdf-bytes")
        document_service.ingest_upload.assert_any_call("notes.txt", "text/plain", b"Beta")
        document_service.ingest_records.assert_called_once_with([record_one, record_two])

        with TestClient(main.app) as client:
            status_response = client.get("/upload/status")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["state"], "completed")

    @patch("main.load_dotenv")
    def test_upload_endpoint_reports_errors_for_unsupported_file_types(self, load_dotenv_mock):
        document_service = MagicMock()
        document_service.ingest_upload.side_effect = api_routes.UnsupportedDocumentTypeError(
            "Unsupported document type: application/zip"
        )

        with patch.object(api_routes, "DocumentService", return_value=document_service):
            with TestClient(main.app) as client:
                response = client.post(
                    "/upload",
                    files=[("files", ("archive.zip", b"zip", "application/zip"))],
                )

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["file_count"], 1)
        self.assertEqual(payload["parsed_count"], 0)
        self.assertEqual(payload["failed_count"], 1)
        self.assertEqual(payload["files"][0]["file_name"], "archive.zip")
        self.assertEqual(payload["files"][0]["status"], "error")
        self.assertEqual(payload["files"][0]["error"], "Unsupported document type: application/zip")
        document_service.ingest_records.assert_not_called()

    @patch("main.load_dotenv")
    def test_upload_endpoint_returns_partial_success_when_one_file_fails(self, load_dotenv_mock):
        good_record = DocumentIngestionRecord(
            file_name="paper-a.pdf",
            content_type="application/pdf",
            source_type="pdf",
            metadata={"page_count": 1},
            text="Alpha",
            chunks=[DocumentChunk(index=0, text="Alpha")],
            parser_name="pypdf",
        )

        document_service = MagicMock()
        document_service.ingest_upload.side_effect = [
            good_record,
            RuntimeError("Limit reached while decompressing."),
        ]
        document_service.ingest_records.return_value = [
            {"file_name": "paper-a.pdf", "status": "completed"},
        ]

        with patch.object(api_routes, "DocumentService", return_value=document_service):
            with TestClient(main.app) as client:
                response = client.post(
                    "/upload",
                    files=[
                        ("files", ("paper-a.pdf", b"pdf-bytes", "application/pdf")),
                        ("files", ("broken.pdf", b"bad-bytes", "application/pdf")),
                    ],
                )

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["file_count"], 2)
        self.assertEqual(payload["parsed_count"], 1)
        self.assertEqual(payload["failed_count"], 1)
        self.assertEqual(len(payload["files"]), 2)
        self.assertEqual(payload["files"][0]["file_name"], "paper-a.pdf")
        self.assertEqual(payload["files"][0]["status"], "parsed")
        self.assertEqual(payload["files"][1]["file_name"], "broken.pdf")
        self.assertEqual(payload["files"][1]["status"], "error")
        self.assertIn("Upload parsing failed", payload["files"][1]["error"])
        self.assertEqual(payload["neo4j"], [{"file_name": "paper-a.pdf", "status": "completed"}])
        document_service.ingest_records.assert_called_once_with([good_record])

        with TestClient(main.app) as client:
            status_response = client.get("/upload/status")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["state"], "partial")

    @patch("main.load_dotenv")
    def test_documents_endpoint_lists_documents(self, load_dotenv_mock):
        document_service = MagicMock()
        document_service.list_documents.return_value = [
            {
                "file_name": "paper-a.pdf",
                "content_type": "application/pdf",
                "source_type": "pdf",
                "parser_name": "pypdf",
                "chunk_count": 4,
                "updated_at": "2026-04-19T12:00:00+00:00",
                "metadata_summary": "page_count=10",
            }
        ]

        with patch.object(api_routes, "DocumentService", return_value=document_service):
            with TestClient(main.app) as client:
                response = client.get("/documents")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["documents"][0]["file_name"], "paper-a.pdf")
        document_service.list_documents.assert_called_once_with()

    @patch("main.load_dotenv")
    def test_delete_document_endpoint_returns_deleted_payload(self, load_dotenv_mock):
        document_service = MagicMock()
        document_service.delete_document.return_value = {
            "deleted": True,
            "file_name": "paper-a.pdf",
            "deleted_count": 2,
        }

        with patch.object(api_routes, "DocumentService", return_value=document_service):
            with TestClient(main.app) as client:
                response = client.delete("/documents/paper-a.pdf")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["deleted"])
        self.assertEqual(payload["deleted_count"], 2)
        document_service.delete_document.assert_called_once_with("paper-a.pdf")

    @patch("main.load_dotenv")
    def test_delete_document_endpoint_returns_404_when_missing(self, load_dotenv_mock):
        document_service = MagicMock()
        document_service.delete_document.return_value = {
            "deleted": False,
            "file_name": "missing.pdf",
            "deleted_count": 0,
        }

        with patch.object(api_routes, "DocumentService", return_value=document_service):
            with TestClient(main.app) as client:
                response = client.delete("/documents/missing.pdf")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 404)
        self.assertIn("No documents found for file name", response.json()["detail"])
        document_service.delete_document.assert_called_once_with("missing.pdf")

    @patch("main.load_dotenv")
    def test_llm_status_endpoint_exposes_client_configuration(self, load_dotenv_mock):
        with TestClient(main.app) as client:
            response = client.get("/llm/status")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn(payload["default_provider"], ["ollama", "llama_cpp"])
        self.assertIn("providers", payload)
        self.assertIn("models", payload)
        self.assertIn("default_model", payload)
        self.assertIn("ollama", payload["providers"])
        self.assertIn("llama_cpp", payload["providers"])
        self.assertIn("openrouter", payload["providers"])
        self.assertIn("default_model", payload["providers"]["ollama"])
        self.assertIn("base_url", payload["providers"]["ollama"])
        self.assertIn("initialized", payload["providers"]["ollama"])

    @patch("main.load_dotenv")
    def test_default_model_prompt_endpoint_returns_generated_text(self, load_dotenv_mock):
        llm_client_service = MagicMock()
        llm_client_service.default_model = "demo-model"
        llm_client_service.default_provider = "ollama"

        completion_message = MagicMock()
        completion_message.content = "Generated answer"
        completion_choice = MagicMock()
        completion_choice.message = completion_message
        completion = MagicMock()
        completion.choices = [completion_choice]

        client = MagicMock()
        client.chat.completions.create.return_value = completion
        llm_client_service.get_client.return_value = client

        with TestClient(main.app) as test_client:
            test_client.app.state.llm_client_service = llm_client_service
            response = test_client.post(
                "/llm/default-model",
                json={
                    "prompt": "Summarize this",
                    "system_prompt": "Be concise",
                    "temperature": 0.2,
                },
            )

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["model"], "demo-model")
        self.assertEqual(payload["provider"], "ollama")
        self.assertEqual(payload["response"], "Generated answer")

        llm_client_service.get_client.assert_called_once_with(model_name="demo-model")
        client.chat.completions.create.assert_called_once()

    @patch("main.load_dotenv")
    def test_default_model_prompt_endpoint_rejects_blank_prompt(self, load_dotenv_mock):
        with TestClient(main.app) as client:
            response = client.post(
                "/llm/default-model",
                json={"prompt": "   "},
            )

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "prompt must not be empty")

    def test_require_env_exits_when_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as exc:
                main.require_env("ZOTERO_LIBRARY_ID")

        self.assertEqual(exc.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
