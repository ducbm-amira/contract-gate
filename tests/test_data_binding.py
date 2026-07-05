#!/usr/bin/env python3
"""Stdlib unittest for port-harness/data_binding_gate.py (DBIND-01, contract-gate #4).

Mirrors greenfield_gate_test.py 1:1 (subprocess harness, case matrix,
stdlib-import test, perf/ReDoS guard) plus the data-binding-specific cases:
row classification (DBIND-03), the three per-data-row checks (DBIND-04 source /
null-column-presence / null-cell / format), unknown-type-is-data, and the
optional delimiter scope (DBIND-02).

Run: cd <repo root> && python3 -m unittest port-harness/data_binding_gate_test.py -v
"""
from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "data_binding.py"
FIXTURES = TESTS_DIR / "fixtures" / "data_binding"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import data_binding as data_binding_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class DataBindingGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 data_binding_gate.py ...`."""

    def test_pass_vn_forgiving(self):
        """VN headers, whitespace/full-width punctuation, static rows (image/
        action) with blank source are skipped -> pass (DBIND-01/03)."""
        r = run_gate("--map", str(FIXTURES / "pass-vn.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_en_with_na_nullhandling(self):
        """EN headers; a data row's null cell is `N/A — always set` (N/A is a
        filled value, NOT a placeholder); a static title row is skipped -> pass."""
        r = run_gate("--map", str(FIXTURES / "pass-en.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_reordered_columns(self):
        """Source/Null/Kind/Element columns NOT in canonical order -> still
        pass (column-reorder tolerance, DBIND-02)."""
        r = run_gate("--map", str(FIXTURES / "pass-reordered.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_delimiter_restricts_scope(self):
        """A broken data table OUTSIDE the <!-- data-binding --> block is
        ignored; only the valid table inside is evaluated -> pass (DBIND-02)."""
        r = run_gate("--map", str(FIXTURES / "pass-delimiter-block.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_empty_source_names_element(self):
        """A data row with a blank source -> exit!=0, stderr names the element."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-source.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("source", r.stderr)
        self.assertIn("assessed val", r.stderr)

    def test_fail_missing_null_column(self):
        """A data table with type+source but no null-handling column -> fail."""
        r = run_gate("--map", str(FIXTURES / "fail-missing-null-col.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("null", r.stderr)

    def test_fail_empty_null_cell(self):
        """Null column present but a data row leaves it blank -> fail."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-null.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("null", r.stderr)

    def test_fail_empty_format_cell(self):
        """Format column exists but a data row leaves it blank -> fail (DBIND-04.3)."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-format.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("format", r.stderr)

    def test_fail_placeholder_source(self):
        """A `?` placeholder source is UNFILLED -> fail (DBIND-04.1)."""
        r = run_gate("--map", str(FIXTURES / "fail-placeholder-source.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_unknown_type_is_gated(self):
        """An unrecognized type (`chip`) is treated as data; blank source
        fails -> exit!=0 (DBIND-03 conservative default)."""
        r = run_gate("--map", str(FIXTURES / "fail-unknown-type-gated.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_no_table(self):
        """No table with both type and source columns -> fail (DBIND-02)."""
        r = run_gate("--map", str(FIXTURES / "fail-no-table.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_empty_file(self):
        """File exists but is whitespace-only -> fail."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-file.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_missing_file(self):
        """Path does not exist -> exit!=0, reason 'data-binding map not found'."""
        r = run_gate("--map", "/nonexistent/x.map.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("data-binding map not found", r.stderr)

    def test_fail_both_forms(self):
        """--map together with --repo/--task is rejected."""
        r = run_gate("--map", "x.md", "--repo", "r", "--task", "t")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that data_binding_gate.py imports nothing
        third-party (DBIND-01)."""
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


class DataBindingGateParserUnitTests(unittest.TestCase):
    """Exercise evaluate_map() directly -- fast, precise, perf/ReDoS guard."""

    def test_multiple_tables_all_evaluated(self):
        """Two per-screen tables; a broken data row in the SECOND table is
        still caught (DBIND-02 scans every qualifying table)."""
        text = (
            "| Screen | Element | Type | Source | Null |\n"
            "|--|--|--|--|--|\n"
            "| a | x | data | `a.x` | hide |\n"
            "\nsome prose\n\n"
            "| Screen | Element | Type | Source | Null |\n"
            "|--|--|--|--|--|\n"
            "| b | y | data |  | hide |\n"
        )
        ok, reason = data_binding_gate.evaluate_map(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("y", reason)

    def test_static_row_with_blank_source_passes(self):
        text = (
            "| Element | Type | Source | Null |\n"
            "|--|--|--|--|\n"
            "| hero image | image |  |  |\n"
            "| name | data | `u.name` | show blank |\n"
        )
        ok, reason = data_binding_gate.evaluate_map(text)
        self.assertTrue(ok, msg=reason)

    def test_zero_data_rows_still_passes(self):
        """A qualifying table with only static rows -> pass (nothing to gate)."""
        text = (
            "| Element | Type | Source | Null |\n"
            "|--|--|--|--|\n"
            "| logo | image |  |  |\n"
        )
        ok, reason = data_binding_gate.evaluate_map(text)
        self.assertTrue(ok, msg=reason)

    def test_perf_large_input_is_linear_and_fast(self):
        header = "| Screen | Element | Type | Source | Null |\n"
        sep = "|--|--|--|--|--|\n"
        rows = "".join(f"| s | e{i} | data | `f.{i}` | hide |\n" for i in range(5000))
        text = header + sep + rows
        start = time.monotonic()
        ok, reason = data_binding_gate.evaluate_map(text)
        elapsed = time.monotonic() - start
        self.assertTrue(ok, msg=reason)
        self.assertLess(elapsed, 1.0, msg=f"parse took {elapsed:.3f}s -- not linear?")

    def test_perf_pathological_input_is_fast_too(self):
        text = "| Type | Source |\n" + (("|" * 200) + ("-" * 200) + "\n") * 500
        start = time.monotonic()
        data_binding_gate.evaluate_map(text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)

    def test_whitespace_only_text_fails(self):
        ok, _ = data_binding_gate.evaluate_map("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _ = data_binding_gate.evaluate_map("")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
