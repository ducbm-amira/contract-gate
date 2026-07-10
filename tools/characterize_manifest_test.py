#!/usr/bin/env python3
"""Stdlib unittest for port-harness/characterize_manifest.py (EVID-02, plan 06-01).

RED-first: written before characterize_manifest.py exists. Mirrors
characterize_pdf_test.py structure (fn-level unit tests over the pure
parse/check core + a subprocess CLI harness via the --text-file escape
hatch) but uses inline-string manifest/text fixtures written to tmp files
instead of a fixtures/ directory, per the plan.

Covers: present, wrong-value MISS (the EVID-02 delta over Sentinel
broken/blank -- a diverging value is caught, not only a missing one),
missing-value MISS, /regex/ form, empty-Observable-never-present, VN/reordered
manifest columns, and the stdlib-only import discipline.

Run: cd <repo root> && python3 port-harness/characterize_manifest_test.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
GATE = HARNESS_DIR / "characterize_manifest.py"

sys.path.insert(0, str(HARNESS_DIR))
import characterize_manifest  # noqa: E402  (import after sys.path setup, RED until file exists)


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


def _write_tmp(text: str, suffix: str) -> Path:
    fd, raw_path = tempfile.mkstemp(suffix=suffix)
    with open(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return Path(raw_path)


# ---- inline field-level Behavior Manifest fixture (EN, canonical shape) ----

MANIFEST_EN = """
| # | Field | Observable |
|---|-------|------------|
| 1 | marker count label | 12 markers found |
| 2 | KPI value | KPI: 1,250 |
| 3 | date stamp | /\\d{4}-\\d{2}-\\d{2}/ |
"""

# VN headers, reordered columns -- format-forgiving parse must still work.
MANIFEST_VN_REORDERED = """
| Observable (oracle để verify) | Hành vi |
|---|---|
| 12 markers found | marker count label |
"""

CAPTURED_TEXT_CORRECT = "marker count label: 12 markers found\nKPI: 1,250\ndate stamp: 2026-07-03\n"
CAPTURED_TEXT_WRONG_VALUE = "marker count label: 12 markers found\nKPI: 999\ndate stamp: 2026-07-03\n"
CAPTURED_TEXT_MISSING_VALUE = "marker count label: 12 markers found\ndate stamp: 2026-07-03\n"


class CharacterizeManifestParserUnitTests(unittest.TestCase):
    """Exercise parse_manifest_rows()/_observable_present()/
    check_manifest_observables() directly -- fast, precise."""

    def setUp(self):
        self.rows = characterize_manifest.parse_manifest_rows(MANIFEST_EN)

    def test_parse_manifest_rows(self):
        self.assertEqual(len(self.rows), 3, msg=f"rows={self.rows!r}")
        labels = [r["label"] for r in self.rows]
        self.assertTrue(any("marker count" in l for l in labels))

    def test_present_when_value_matches(self):
        results = characterize_manifest.check_manifest_observables(
            CAPTURED_TEXT_CORRECT, self.rows
        )
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertTrue(r["present"], msg=f"expected present: {r!r}")

    def test_wrong_value_is_a_miss(self):
        """A manifest Observable value that DIFFERS from the captured text
        (wrong value) -> MISS -- this is the EVID-02 delta over Sentinel
        broken/blank: a diverging value is caught, not only a missing one."""
        results = characterize_manifest.check_manifest_observables(
            CAPTURED_TEXT_WRONG_VALUE, self.rows
        )
        absent = [r for r in results if not r["present"]]
        self.assertEqual(len(absent), 1, msg=f"results={results!r}")
        self.assertIn("1,250", absent[0]["observable"])

    def test_missing_value_is_a_miss(self):
        """A manifest Observable absent entirely from the captured text -> MISS."""
        results = characterize_manifest.check_manifest_observables(
            CAPTURED_TEXT_MISSING_VALUE, self.rows
        )
        absent = [r for r in results if not r["present"]]
        self.assertEqual(len(absent), 1, msg=f"results={results!r}")
        self.assertIn("1,250", absent[0]["observable"])

    def test_regex_observable(self):
        regex_row = [r for r in self.rows if r["observable"].strip().startswith("/")]
        self.assertEqual(len(regex_row), 1, msg=f"rows={self.rows!r}")
        present = characterize_manifest.check_manifest_observables(
            CAPTURED_TEXT_CORRECT, regex_row
        )
        self.assertTrue(present[0]["present"])
        absent = characterize_manifest.check_manifest_observables(
            "no date here at all", regex_row
        )
        self.assertFalse(absent[0]["present"])

    def test_empty_observable_never_present(self):
        self.assertFalse(characterize_manifest._observable_present("", "anything at all"))
        self.assertFalse(characterize_manifest._observable_present("-", "anything at all"))

    def test_vn_reordered_columns_parse(self):
        rows = characterize_manifest.parse_manifest_rows(MANIFEST_VN_REORDERED)
        self.assertEqual(len(rows), 1, msg=f"rows={rows!r}")
        self.assertIn("12 markers found", rows[0]["observable"])


class CharacterizeManifestCLITests(unittest.TestCase):
    """CLI-level cases via the required --text-file argument -- exercises the
    real `python3 characterize_manifest.py ...` entrypoint."""

    def _run_cli(self, manifest_text: str, captured_text: str) -> subprocess.CompletedProcess:
        m = _write_tmp(manifest_text, ".manifest.md")
        t = _write_tmp(captured_text, ".txt")
        self.addCleanup(lambda: m.unlink(missing_ok=True))
        self.addCleanup(lambda: t.unlink(missing_ok=True))
        return run_gate("--manifest", str(m), "--text-file", str(t))

    def test_cli_exit_zero_on_correct(self):
        r = self._run_cli(MANIFEST_EN, CAPTURED_TEXT_CORRECT)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("all rows present", r.stdout)

    def test_cli_exit_nonzero_on_wrong_value(self):
        r = self._run_cli(MANIFEST_EN, CAPTURED_TEXT_WRONG_VALUE)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("VERDICT", r.stdout)
        self.assertIn("MISS", r.stdout)

    def test_cli_fail_missing_manifest(self):
        t = _write_tmp(CAPTURED_TEXT_CORRECT, ".txt")
        self.addCleanup(lambda: t.unlink(missing_ok=True))
        r = run_gate("--manifest", "/nonexistent/x.manifest.md", "--text-file", str(t))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("manifest not found", r.stderr)

    def test_cli_fail_requires_text_file(self):
        m = _write_tmp(MANIFEST_EN, ".manifest.md")
        self.addCleanup(lambda: m.unlink(missing_ok=True))
        r = run_gate("--manifest", str(m))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--text-file", r.stderr)


class CharacterizeManifestImportTests(unittest.TestCase):
    def test_stdlib_only_import(self):
        """Grep-level confirmation that characterize_manifest.py imports
        nothing third-party (mirrors characterize_pdf_test.py's equivalent)."""
        src = GATE.read_text(encoding="utf-8")
        stdlib_ok_prefixes = (
            "import argparse",
            "import re",
            "import sys",
            "from pathlib",
            "from __future__",
        )
        import_lines = [
            line.strip()
            for line in src.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            self.assertTrue(
                any(line.startswith(p) for p in stdlib_ok_prefixes),
                msg=f"non-stdlib-looking import found: {line!r}",
            )


if __name__ == "__main__":
    unittest.main()
