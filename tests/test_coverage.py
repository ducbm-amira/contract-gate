#!/usr/bin/env python3
"""Stdlib unittest for contract_gate/gates/coverage.py (D-20).

Ported from port-harness/coverage_gate_test.py into the repo's subprocess-harness
style (mirrors tests/test_data_binding.py): a real `python3 coverage.py ...` CLI
harness + direct evaluate_coverage() unit calls, a stdlib-only import guard, and a
--dir mtime-resolution test (the ported resolver now picks the NEWEST report by
mtime, not the alphabetically-last name).

Run: cd <repo root> && python3 -m unittest tests.test_coverage -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "coverage.py"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import coverage as coverage_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


# ---- inline REPORT.md fixtures ----

FULL = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | text | data |
|-----|----------|--------|---------|------|------|
| step5 | TC-B01 | TC-L02 | TC-F03 | TC-T04 | TC-D05 |
| step7 | TC-B06 | N/A:trống | BOUNDARY:backend down | TC-T07 | N/A |
<!-- coverage-matrix:end -->
"""

MISSING_TEXT = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | data |
|-----|----------|--------|---------|------|
| step5 | TC-B01 | TC-L02 | TC-F03 | TC-D05 |
<!-- coverage-matrix:end -->
"""

EMPTY_CELL = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | text | data |
|-----|----------|--------|---------|------|------|
| step5 | TC-B01 | TC-L02 | TC-F03 |  | TC-D05 |
<!-- coverage-matrix:end -->
"""

PLACEHOLDER_CELL = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | text | data |
|-----|----------|--------|---------|------|------|
| step5 | TC-B01 | TC-L02 | TC-F03 | TODO | TC-D05 |
<!-- coverage-matrix:end -->
"""

NO_BLOCK = "# QA Report\n\nĐã test PDF, mọi thứ ngon.\n"

VN_HEADER_REORDERED = """
<!-- coverage-matrix:start -->
| màn | dữ liệu | chữ/label | chức năng | bố cục | hành vi |
|---|---|---|---|---|---|
| PDF | TC-D1 | TC-T1 | TC-F1 | TC-L1 | TC-B1 |
<!-- coverage-matrix:end -->
"""

GROUPED_PLUS = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | text | data |
|-----|----------|--------|---------|------|------|
| map+list | TC-B01 | TC-L02 | TC-F03 | TC-T04 | TC-D05 |
<!-- coverage-matrix:end -->
"""

GROUPED_RANGE = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | text | data |
|-----|----------|--------|---------|------|------|
| step5-9 | TC-B01 | TC-L02 | TC-F03 | TC-T04 | TC-D05 |
<!-- coverage-matrix:end -->
"""

PER_SCREEN_SPLIT = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | text | data |
|-----|----------|--------|---------|------|------|
| map | TC-B01 | TC-L02 | TC-F03 | TC-T04 | TC-D05 |
| list | TC-B06 | TC-L07 | TC-F08 | TC-T09 | TC-D10 |
<!-- coverage-matrix:end -->
"""

HYPHEN_SINGLE_OK = """
<!-- coverage-matrix:start -->
| màn | behavior | layout | feature | text | data |
|-----|----------|--------|---------|------|------|
| deal/map | TC-B01 | TC-L02 | TC-F03 | TC-T04 | TC-D05 |
| step-5 | TC-B06 | TC-L07 | TC-F08 | TC-T09 | TC-D10 |
<!-- coverage-matrix:end -->
"""


def _write_tmp_report(text: str) -> Path:
    fd, raw_path = tempfile.mkstemp(suffix=".REPORT.md")
    with open(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return Path(raw_path)


class CoverageGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 coverage.py ...` entrypoint."""

    def _run(self, text: str) -> subprocess.CompletedProcess:
        p = _write_tmp_report(text)
        self.addCleanup(lambda: p.unlink(missing_ok=True))
        return run_gate("--report", str(p))

    def test_pass_full_matrix(self):
        r = self._run(FULL)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_missing_text_column(self):
        r = self._run(MISSING_TEXT)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("text", r.stderr)

    def test_fail_empty_cell(self):
        r = self._run(EMPTY_CELL)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_placeholder_todo(self):
        r = self._run(PLACEHOLDER_CELL)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_no_block(self):
        r = self._run(NO_BLOCK)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_pass_vn_header_reordered(self):
        r = self._run(VN_HEADER_REORDERED)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_grouped_plus_label(self):
        r = self._run(GROUPED_PLUS)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_grouped_numeric_range_label(self):
        r = self._run(GROUPED_RANGE)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_pass_per_individual_screen_split(self):
        r = self._run(PER_SCREEN_SPLIT)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_legit_hyphen_slash_single_screen(self):
        r = self._run(HYPHEN_SINGLE_OK)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_missing_file(self):
        r = run_gate("--report", "/nonexistent/x.REPORT.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("report not found", r.stderr)

    def test_fail_both_args_given(self):
        p = _write_tmp_report(FULL)
        self.addCleanup(lambda: p.unlink(missing_ok=True))
        r = run_gate("--report", str(p), "--dir", str(p.parent))
        self.assertNotEqual(r.returncode, 0)

    def test_fail_neither_arg_given(self):
        r = run_gate()
        self.assertNotEqual(r.returncode, 0)

    def test_dir_resolves_latest_report_by_mtime(self):
        """--dir picks the NEWEST report by mtime, not the alphabetically-last
        name (the ported behavior fix). An older, alphabetically-later filename
        with a FAILING body must NOT be preferred over a newer PASSING one."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [f.unlink() for f in d.glob("*")] and d.rmdir())
        # 'z-REPORT.md' sorts last alphabetically but is OLDER + failing.
        older = d / "z-REPORT.md"
        older.write_text(MISSING_TEXT, encoding="utf-8")
        import os
        old_time = time.time() - 100
        os.utime(older, (old_time, old_time))
        # 'a-REPORT.md' sorts first alphabetically but is NEWER + passing.
        newer = d / "a-REPORT.md"
        newer.write_text(FULL, encoding="utf-8")
        r = run_gate("--dir", str(d))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that coverage.py imports nothing third-party."""
        src = GATE.read_text(encoding="utf-8")
        stdlib_ok_prefixes = ("import argparse", "import sys", "from pathlib", "from __future__")
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


class CoverageGateParserUnitTests(unittest.TestCase):
    """Exercise evaluate_coverage() directly -- fast, precise, perf/ReDoS guard."""

    def test_full_matrix_pass(self):
        ok, reason = coverage_gate.evaluate_coverage(FULL)
        self.assertTrue(ok, msg=reason)

    def test_missing_text_fails(self):
        ok, reason = coverage_gate.evaluate_coverage(MISSING_TEXT)
        self.assertFalse(ok, msg=reason)
        self.assertIn("text", reason)

    def test_whitespace_only_text_fails(self):
        ok, _ = coverage_gate.evaluate_coverage("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _ = coverage_gate.evaluate_coverage("")
        self.assertFalse(ok)

    def test_perf_large_input_is_linear_and_fast(self):
        header = "| màn | behavior | layout | feature | text | data |\n"
        sep = "|---|---|---|---|---|---|\n"
        rows = "".join(
            f"| step{i} | TC-B{i} | TC-L{i} | TC-F{i} | TC-T{i} | TC-D{i} |\n"
            for i in range(5000)
        )
        text = coverage_gate.START + "\n" + header + sep + rows + coverage_gate.END
        start = time.monotonic()
        ok, reason = coverage_gate.evaluate_coverage(text)
        elapsed = time.monotonic() - start
        self.assertTrue(ok, msg=reason)
        self.assertLess(elapsed, 1.0, msg=f"parse took {elapsed:.3f}s -- not linear?")

    def test_perf_pathological_input_is_fast_too(self):
        text = coverage_gate.START + "\n" + (("|" * 200) + ("-" * 200) + "\n") * 500 + coverage_gate.END
        start = time.monotonic()
        coverage_gate.evaluate_coverage(text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()
