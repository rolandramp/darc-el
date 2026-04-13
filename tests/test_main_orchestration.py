import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import main


class MainOrchestrationTests(unittest.TestCase):
    @patch("main.load_dotenv")
    @patch("main.ZoteroDownloadService")
    @patch("main.require_env")
    def test_main_delegates_download_and_save(
        self, require_env_mock, service_cls_mock, load_dotenv_mock
    ):
        require_env_mock.side_effect = ["library-id", "api-key"]
        service_instance = MagicMock()
        service_instance.download_items.return_value = [
            {"data": {"itemType": "book", "key": "ABC", "title": "Demo"}}
        ]
        service_cls_mock.return_value = service_instance

        with patch("sys.stdout", new_callable=io.StringIO) as output, patch.dict(
            "os.environ",
            {
                "ZOTERO_LIBRARY_TYPE": "group",
                "ZOTERO_OUTPUT_FILE": "output.json",
            },
            clear=False,
        ):
            main.main()

        load_dotenv_mock.assert_called_once()
        service_cls_mock.assert_called_once_with(
            library_id="library-id",
            api_key="api-key",
            library_type="group",
        )
        service_instance.download_items.assert_called_once_with()
        service_instance.save_items_to_file.assert_called_once_with(
            service_instance.download_items.return_value, "output.json"
        )
        self.assertIn("Downloaded 1 item(s)", output.getvalue())

    def test_require_env_exits_when_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as exc:
                main.require_env("ZOTERO_LIBRARY_ID")

        self.assertEqual(exc.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
