#!/usr/bin/env python3
"""Stdlib unittest for port-harness/characterize_pdf.py (GREEN-02, plan 05-02).

Covers: present-AND-correct for target=pdf rows (test_all_present), the
wrong-value catch that proves the assertion fails when the behavior is wrong
(test_wrong_value_caught, SC#3), the CLI exit-code contract via --text-file
(test_cli_exit_*), a /regex/-form Observable (test_regex_observable), a real
pdftotext integration test guarded by shutil.which (skips cleanly without
poppler), and the stdlib-only import discipline (test_stdlib_only_import).

Run: cd <repo root> && python3 -m unittest port-harness/characterize_pdf_test.py -v
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
GATE = HARNESS_DIR / "characterize_pdf.py"
FIXTURES = HARNESS_DIR / "fixtures" / "characterize_pdf"
SPEC = FIXTURES / "sample.spec.md"
CORRECT_TEXT = FIXTURES / "extracted-correct.txt"
WRONG_TEXT = FIXTURES / "extracted-wrong.txt"

sys.path.insert(0, str(HARNESS_DIR))
import characterize_pdf  # noqa: E402  (import after sys.path setup)


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


class CharacterizePdfParserUnitTests(unittest.TestCase):
    """Exercise parse_pdf_rows()/check_pdf_observables() directly -- fast,
    precise, and the "pure core" the plan calls out as unit-testable without
    requiring pdftotext at all."""

    def setUp(self):
        self.spec_text = SPEC.read_text(encoding="utf-8")
        self.rows = characterize_pdf.parse_pdf_rows(self.spec_text)

    def test_parse_pdf_rows_excludes_web(self):
        """Only target=pdf rows are returned; the web row is excluded (D-07)."""
        labels = [r["label"] for r in self.rows]
        self.assertEqual(len(self.rows), 3, msg=f"rows={self.rows!r}")
        self.assertTrue(any("お問い合わせ" in l for l in labels))
        self.assertFalse(any("web-only" in l.lower() for l in labels))
        self.assertFalse(any("Chart legend" in l for l in labels))

    def test_all_present(self):
        """Correct extracted text -> every target=pdf row's Observable is present."""
        text = CORRECT_TEXT.read_text(encoding="utf-8")
        results = characterize_pdf.check_pdf_observables(text, self.rows)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertTrue(r["present"], msg=f"expected present: {r!r}")

    def test_wrong_value_caught(self):
        """Wrong-value text -> exactly the diverging KPI row is reported absent
        (proves the assertion FAILS when the behavior is wrong, SC#3) -- the
        other two rows (unaffected by the KPI edit) stay present."""
        text = WRONG_TEXT.read_text(encoding="utf-8")
        results = characterize_pdf.check_pdf_observables(text, self.rows)
        absent = [r for r in results if not r["present"]]
        self.assertEqual(len(absent), 1, msg=f"results={results!r}")
        self.assertIn("1,250", absent[0]["observable"])
        present_labels = [r["label"] for r in results if r["present"]]
        self.assertEqual(len(present_labels), 2)

    def test_regex_observable(self):
        """A `/regex/` Observable matches in correct text, is absent in text
        lacking the pattern."""
        regex_row = [r for r in self.rows if r["observable"].startswith("/")]
        self.assertEqual(len(regex_row), 1, msg=f"rows={self.rows!r}")
        correct_text = CORRECT_TEXT.read_text(encoding="utf-8")
        present = characterize_pdf.check_pdf_observables(correct_text, regex_row)
        self.assertTrue(present[0]["present"])

        no_date_text = "売却活動報告書\nお問い合わせ\n閲覧数（KPI）: 1,250\n"
        absent = characterize_pdf.check_pdf_observables(no_date_text, regex_row)
        self.assertFalse(absent[0]["present"])


class CharacterizePdfCLITests(unittest.TestCase):
    """CLI-level cases via the --text-file escape hatch -- exercises the real
    `python3 characterize_pdf.py ...` entrypoint without depending on a real
    PDF fixture existing."""

    def test_cli_exit_zero_on_correct(self):
        r = run_gate("--spec", str(SPEC), "--text-file", str(CORRECT_TEXT))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("all rows present", r.stdout)

    def test_cli_exit_nonzero_on_wrong(self):
        r = run_gate("--spec", str(SPEC), "--text-file", str(WRONG_TEXT))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("KPI", r.stdout)
        self.assertIn("MISS", r.stdout)

    def test_cli_fail_missing_spec(self):
        r = run_gate("--spec", "/nonexistent/x.spec.md", "--text-file", str(CORRECT_TEXT))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("spec not found", r.stderr)

    def test_cli_fail_requires_pdf_or_text_file(self):
        r = run_gate("--spec", str(SPEC))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--pdf or --text-file", r.stderr)


class CharacterizePdfIntegrationTests(unittest.TestCase):
    """Real pdftotext integration -- guarded by shutil.which, skips cleanly
    on machines without poppler installed."""

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext (poppler-utils) not installed")
    def test_pdftotext_integration(self):
        import tempfile

        pdf_bytes = _minimal_pdf_with_text("Hello PDF Test 1,250")
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "sample.pdf"
            pdf_path.write_bytes(pdf_bytes)
            text = characterize_pdf.extract_pdf_text(str(pdf_path))
            self.assertIn("Hello PDF Test", text)
            self.assertIn("1,250", text)


def _minimal_pdf_with_text(text: str) -> bytes:
    """Build a minimal single-page PDF embedding `text` via a raw content
    stream, with no third-party PDF library — just enough structure
    (Catalog/Pages/Page/Font/Contents + a linear xref table) for pdftotext
    to extract the text back out. ASCII-only content is assumed."""
    content = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("ascii")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 300 200] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    n = len(objs) + 1
    out += f"xref\n0 {n}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n" + f"<< /Size {n} /Root 1 0 R >>\n".encode()
    out += b"startxref\n" + f"{xref_offset}\n".encode() + b"%%EOF"
    return bytes(out)


class CharacterizePdfImportTests(unittest.TestCase):
    def test_stdlib_only_import(self):
        """Grep-level confirmation that characterize_pdf.py imports nothing
        third-party (mirrors manifest_gate_test.py's equivalent check)."""
        src = GATE.read_text(encoding="utf-8")
        stdlib_ok_prefixes = (
            "import argparse",
            "import re",
            "import shutil",
            "import subprocess",
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
