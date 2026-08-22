import json, tempfile, unittest
from pathlib import Path

from actions.file_router import FileRouter
from actions.folder_scan import scan_folder
from actions.fis_parser import parse_actions
from ledger import Ledger


class CoreTests(unittest.TestCase):
    def test_move_receipt_and_undo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "a.txt"; source.write_text("hello")
            router = FileRouter(root, Ledger(root / "ledger.sqlite")); destination = root / "done" / "a.txt"
            preview = router.move(source, destination)
            self.assertEqual(preview["status"], "dry_run"); self.assertTrue(source.exists())
            router.move(source, destination, dry_run=False)
            self.assertTrue(destination.exists()); router.undo()
            self.assertTrue(source.exists()); self.assertFalse(destination.exists())

    def test_scan_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "a.txt").write_text("same"); (root / "b.txt").write_text("same")
            manifest = scan_folder(root)
            self.assertEqual(manifest["file_count"], 2); self.assertEqual(len(manifest["duplicates"]), 1)

    def test_fis_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "fis.html"
            page.write_text('<div class="action-item" data-operation="move" data-source="a" data-dest="b" data-approved="true">Move it</div>')
            self.assertEqual(parse_actions(page)[0]["destination"], "b")

    def test_ledger_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / "ledger.sqlite")
            ledger.record("api_call", provider="test", status="success", input_tokens=2, output_tokens=3, cost_usd=.1)
            self.assertEqual(ledger.stats()[0]["total_input_tokens"], 2)


if __name__ == "__main__": unittest.main()
