import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import main
from fastapi.testclient import TestClient


class MainOrchestrationTests(unittest.TestCase):
    def setUp(self):
        main.app.state.download_status = main._create_default_download_status()

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
            main.ZoteroDownloadService,
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
            main.ZoteroDownloadService,
            "from_download_request",
            side_effect=ValueError("Missing Zotero library ID"),
        ):
            with TestClient(main.app) as client:
                response = client.post("/download")

        load_dotenv_mock.assert_called_once()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Missing Zotero library ID")

    def test_require_env_exits_when_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as exc:
                main.require_env("ZOTERO_LIBRARY_ID")

        self.assertEqual(exc.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
