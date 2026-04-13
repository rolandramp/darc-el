import json
import tempfile
import unittest
import importlib.util
from pathlib import Path

import sys

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
SERVICE_PATH = SRC_ROOT / "darc-el" / "service" / "download_service.py"
SPEC = importlib.util.spec_from_file_location("download_service", SERVICE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError("Could not load download_service module")
DOWNLOAD_SERVICE_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOWNLOAD_SERVICE_MODULE)
ZoteroDownloadService = DOWNLOAD_SERVICE_MODULE.ZoteroDownloadService


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


if __name__ == "__main__":
    unittest.main()
