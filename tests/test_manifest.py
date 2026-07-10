#!/usr/bin/env python3
"""Stdlib unittest for port-harness/manifest_gate.py (PORT-02, plan 02-01).

RED-first: this file is written BEFORE manifest_gate.py exists / fixtures are
authored (TDD RED). Once manifest_gate.py + the six fixtures under
fixtures/manifest_gate/ are implemented, every case below goes green.

Covers: pass-vn (+ folded-in pass-forgiving: whitespace/VN prose/full-width
punctuation in Observable), pass-en (header-variant, D-05), pass-reordered
(column-reorder tolerance, D-05), fail-empty-observable (D-04.3, names the
offending row), fail-empty-file (D-04.1), fail-missing-file (asserted
programmatically, no fixture), fail-no-table (D-04.2), and the T-02-01
perf/ReDoS guard (>=5000-row + pathological input, linear parse, <1s).

Run: cd <repo root> && python3 -m unittest port-harness/manifest_gate_test.py -v
"""
from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "manifest.py"
FIXTURES = TESTS_DIR / "fixtures" / "manifest"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import manifest as manifest_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class ManifestGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 manifest_gate.py ...` entrypoint,
    matching the plan's acceptance_criteria commands 1:1."""

    def test_pass_vn_forgiving(self):
        """VN headers; Observable cells carry extra whitespace, VN prose, and
        full-width punctuation (pass-forgiving folded into pass-vn, D-05) -> pass."""
        r = run_gate("--manifest", str(FIXTURES / "pass-vn.manifest.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_en_header_variant(self):
        """EN header variant (Behavior/Type/Observable/Ported?) -> pass (D-05)."""
        r = run_gate("--manifest", str(FIXTURES / "pass-en.manifest.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_reordered_columns(self):
        """Observable column NOT last -> still pass (column-reorder tolerance, D-05)."""
        r = run_gate("--manifest", str(FIXTURES / "pass-reordered.manifest.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_empty_observable_names_row(self):
        """At least one behavior row has an empty Observable cell -> exit!=0,
        stderr says fail + names the offending row (D-04.3)."""
        r = run_gate("--manifest", str(FIXTURES / "fail-empty-observable.manifest.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_fail_empty_file(self):
        """File exists but is empty/whitespace -> exit!=0 (D-04.1)."""
        r = run_gate("--manifest", str(FIXTURES / "fail-empty-file.manifest.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_no_table(self):
        """Non-empty file, no recognizable behavior table -> exit!=0 (D-04.2)."""
        r = run_gate("--manifest", str(FIXTURES / "fail-no-table.manifest.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_pass_multi_table_master_manifest(self):
        """D-07: a master manifest with 2 page-sections, each its own table,
        both valid -> pass, counting rows from BOTH tables."""
        r = run_gate("--manifest", str(FIXTURES / "pass-multi-table-master-manifest.manifest.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)
        self.assertIn("2 behavior row(s) verified across 2 table(s)", r.stdout)

    def test_fail_multi_table_violation_in_later_table_not_missed(self):
        """D-07 regression guard: an empty Observable in the SECOND table of
        a multi-table master manifest must fail the gate (not be silently
        skipped because table 1 already passed) -- names the page heading."""
        r = run_gate("--manifest", str(FIXTURES / "fail-multi-table-second-table-violation.manifest.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Page 2", r.stderr)

    def test_fail_missing_file(self):
        """Path does not exist -> exit!=0, reason 'manifest not found'.
        No fixture -- exercised with a nonexistent path per the plan."""
        r = run_gate("--manifest", "/nonexistent/x.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("manifest not found", r.stderr)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that manifest_gate.py imports nothing
        third-party (D-01) -- redundant with the shell acceptance check but
        keeps the prohibition enforced in the test suite itself."""
        src = GATE.read_text(encoding="utf-8")
        stdlib_ok_prefixes = ("import argparse", "import sys", "import re", "from pathlib", "from __future__", "from .. import tableparse", "from contract_gate import tableparse")
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


class ManifestGateParserUnitTests(unittest.TestCase):
    """Exercise evaluate_manifest() directly (no subprocess) -- fast, precise,
    used for the perf/ReDoS guard and small parser edge cases."""

    def test_fail_placeholder_observable(self):
        """F2 regression (2026-07-11): an Observable of `TODO`/`?` is an
        UNFILLED cell, not a pass — before the shared empty-cell rule this
        gate only checked dash look-alikes and both PASSED (false PASS)."""
        for bad in ("TODO", "?", "TBD", "? not sure yet", "TODO: ask BE"):
            text = (
                "| # | Behavior | Observable |\n"
                "|--|--|--|\n"
                f"| 1 | click X | {bad} |\n"
            )
            ok, reason = manifest_gate.evaluate_manifest(text)
            self.assertFalse(ok, msg=f"placeholder {bad!r} passed: {reason}")
            self.assertIn("empty Observable", reason)

    def test_fail_abutting_table_graded_with_own_columns(self):
        """F4 regression (2026-07-11): a second table glued directly under
        the first (no blank line), with a DIFFERENT column order, used to be
        consumed as body rows of table 1 and graded under table 1's column
        indices — its empty Observable was invisible (false PASS)."""
        text = (
            "| # | Behavior | Observable |\n"
            "|--|--|--|\n"
            "| 1 | x | dom check |\n"
            "| # | Observable | Behavior |\n"
            "|--|--|--|\n"
            "| 2 | - | click y |\n"
        )
        ok, reason = manifest_gate.evaluate_manifest(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("empty Observable", reason)

    def test_fail_abutting_table_after_non_qualifying_table(self):
        """F4 regression, other order: a qualifying table glued under a
        NON-qualifying one must still be found and graded."""
        text = (
            "| Note | Comment |\n"
            "|--|--|\n"
            "| a | b |\n"
            "| # | Behavior | Observable |\n"
            "|--|--|--|\n"
            "| 1 | x |  |\n"
        )
        ok, reason = manifest_gate.evaluate_manifest(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("empty Observable", reason)

    def test_fail_header_only_table_in_multi_table_file(self):
        """F7: a header-only table (0 rows) among filled ones is an ungraded
        claim — it must fail, naming the empty table."""
        text = (
            "## Page 1\n"
            "| # | Behavior | Observable |\n"
            "|--|--|--|\n"
            "| 1 | x | dom check |\n"
            "\n"
            "## Page 2\n"
            "| # | Behavior | Observable |\n"
            "|--|--|--|\n"
        )
        ok, reason = manifest_gate.evaluate_manifest(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("Page 2", reason)
        self.assertIn("no rows", reason)

    def test_pass_escaped_pipe_in_cell(self):
        """F6: `\\|` is one cell's content, not a column break — before the
        shared split_row an escaped pipe shifted every later column."""
        text = (
            "| # | Behavior | Observable |\n"
            "|--|--|--|\n"
            "| 1 | toggle a \\| b | shows a or b |\n"
        )
        ok, reason = manifest_gate.evaluate_manifest(text)
        self.assertTrue(ok, msg=reason)

    def test_perf_large_input_is_linear_and_fast(self):
        header = "| # | Hành vi | Loại | Observable (oracle để verify) | Đã port? |\n"
        sep = "|---|---|---|---|---|\n"
        rows = "".join(
            f"| {i} | hành vi {i} | visible | DOM text {i} | x |\n" for i in range(5000)
        )
        text = header + sep + rows
        start = time.monotonic()
        ok, reason = manifest_gate.evaluate_manifest(text)
        elapsed = time.monotonic() - start
        self.assertTrue(ok, msg=reason)
        self.assertLess(elapsed, 1.0, msg=f"parse took {elapsed:.3f}s -- not linear?")

    def test_perf_pathological_input_is_fast_too(self):
        """Adversarial pipes/dashes that would blow up a catastrophic-backtracking
        regex; a linear parser must still finish comfortably under 1s (T-02-01)."""
        text = "| Observable |\n" + (("|" * 200) + ("-" * 200) + "\n") * 500
        start = time.monotonic()
        manifest_gate.evaluate_manifest(text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)

    def test_whitespace_only_text_fails(self):
        ok, _reason = manifest_gate.evaluate_manifest("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _reason = manifest_gate.evaluate_manifest("")
        self.assertFalse(ok)

    def test_findings_all_report_every_table_not_just_first(self):
        """D-07 + `--all`: findings() must surface a violation from a LATER
        table, not stop after the first table's rows are exhausted."""
        path = FIXTURES / "fail-multi-table-second-table-violation.manifest.md"
        text = path.read_text(encoding="utf-8")
        out = manifest_gate.findings(text, path)
        self.assertEqual(len(out), 1, msg=f"expected 1 finding (page 2's row), got: {out}")
        self.assertIn("Page 2", out[0])


if __name__ == "__main__":
    unittest.main()
