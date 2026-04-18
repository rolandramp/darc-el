import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import main
from api import routes as api_routes
from core.document_ingestion import DocumentChunk, DocumentIngestionRecord
from fastapi.testclient import TestClient


class MainOrchestrationTests(unittest.TestCase):
    def setUp(self):
        main.initialize_app_state(main.app)

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

        ingestion_service = MagicMock()
        ingestion_service.ingest_upload.side_effect = [record_one, record_two]
        neo4j_service = MagicMock()
        neo4j_service.ingest_documents.return_value = [
            {"file_name": "paper-a.pdf", "status": "completed"},
            {"file_name": "notes.txt", "status": "completed"},
        ]

        with patch.object(api_routes, "DocumentIngestionService", return_value=ingestion_service):
            with patch.object(api_routes, "Neo4jDocumentService", return_value=neo4j_service):
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
        self.assertEqual(len(payload["files"]), 2)
        ingestion_service.ingest_upload.assert_any_call("paper-a.pdf", "application/pdf", b"pdf-bytes")
        ingestion_service.ingest_upload.assert_any_call("notes.txt", "text/plain", b"Beta")
        neo4j_service.ingest_documents.assert_called_once_with([record_one, record_two])

        with TestClient(main.app) as client:
            status_response = client.get("/upload/status")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["state"], "completed")

    @patch("main.load_dotenv")
    def test_upload_endpoint_rejects_unsupported_file_types(self, load_dotenv_mock):
        ingestion_service = MagicMock()
        ingestion_service.ingest_upload.side_effect = api_routes.UnsupportedDocumentTypeError(
            "Unsupported document type: application/zip"
        )

        with patch.object(api_routes, "DocumentIngestionService", return_value=ingestion_service):
            with TestClient(main.app) as client:
                response = client.post(
                    "/upload",
                    files=[("files", ("archive.zip", b"zip", "application/zip"))],
                )

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["detail"], "Unsupported document type: application/zip")

    def test_require_env_exits_when_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as exc:
                main.require_env("ZOTERO_LIBRARY_ID")

        self.assertEqual(exc.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
