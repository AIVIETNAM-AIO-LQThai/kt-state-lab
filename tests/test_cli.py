import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ktlab.data.cli import main, run_pipeline
from tests.support import FIXTURE, HEADER, row, write_csv


class CliTests(unittest.TestCase):
    def test_run_pipeline_writes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_pipeline(FIXTURE, Path(tmp))
            splits = Path(tmp) / "splits"
            eda = Path(tmp) / "eda"
            for path in (
                Path(tmp) / "data_quality.json",
                splits / "manifest.json",
                splits / "id_maps.json",
                splits / "train.csv",
                splits / "val.csv",
                splits / "test.csv",
                splits / "cs_s_examples.csv",
                eda / "eda_summary.json",
                eda / "kc_transitions.csv",
            ):
                self.assertTrue(path.exists(), str(path))
            quality = json.loads((Path(tmp) / "data_quality.json").read_text(encoding="utf-8"))
            self.assertTrue(quality["ok"])
            self.assertEqual(quality["rows_rejected"], 0)
            counts = manifest["counts"]["interactions"]
            self.assertEqual(sum(counts.values()), 30)
            self.assertEqual(
                manifest["source_sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
            )

    def test_main_returns_zero_on_valid_input(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--input", str(FIXTURE), "--out", tmp]), 0)

    def test_main_returns_two_on_contract_error(self):
        path = write_csv(HEADER + "\n" + row(correct=7) + "\n")
        try:
            with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--input", str(path), "--out", tmp]), 2)
        finally:
            path.unlink()

    def test_allow_invalid_drops_rows_and_reports_them(self):
        text = (
            HEADER
            + "\n"
            + row(student="s1", interaction="i1", step=1)
            + "\n"
            + row(student="s1", interaction="i1", step=2)
            + "\n"
            + row(student="s2", interaction="i2", step=1)
            + "\n"
            + row(student="s3", interaction="i3", step=1)
            + "\n"
        )
        path = write_csv(text)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_pipeline(path, Path(tmp), allow_invalid=True)
                quality = json.loads((Path(tmp) / "data_quality.json").read_text(encoding="utf-8"))
                self.assertFalse(quality["ok"])
                self.assertEqual(quality["rows_rejected"], 1)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
