#!/usr/bin/env python3
"""Stdlib unittest for contract_gate/gates/fidelity.py (FID-01, gate #5).

Mirrors test_golden_record.py 1:1 (subprocess CLI harness, case matrix,
stdlib-import test, perf/ReDoS guard) plus the fidelity-specific cases: the
Screen/Report table shape, resolving a Report cell relative to the contract
file's own directory (FID-04), grading an ALREADY-WRITTEN report JSON rather
than trusting a hand-typed verdict, and the report-schema edge cases
(missing/malformed/unexpected `overall`).

Run: cd <repo root> && python3 -m unittest tests/test_fidelity.py -v
"""
from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "fidelity.py"
FIXTURES = TESTS_DIR / "fixtures" / "fidelity"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import fidelity as fidelity_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class FidelityGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 fidelity.py ...`."""

    def test_pass_en(self):
        r = run_gate("--contract", str(FIXTURES / "pass-en.contract.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_vn_headers(self):
        r = run_gate("--contract", str(FIXTURES / "pass-vn.contract.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_reordered_columns(self):
        r = run_gate("--contract", str(FIXTURES / "pass-reordered.contract.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_delimiter_restricts_scope(self):
        """A table with an empty Report cell OUTSIDE the <!-- fidelity -->
        block is ignored; only the passing row inside is evaluated."""
        r = run_gate("--contract", str(FIXTURES / "pass-delimiter-block.contract.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_report_path_resolved_relative_to_contract_dir(self):
        """`reports/pass.report.json` in the contract resolves against the
        contract file's OWN directory (FID-04), not the CWD the gate is
        invoked from — proven by running from the repo root, not FIXTURES."""
        r = subprocess.run(
            [sys.executable, str(GATE), "--contract", str(FIXTURES / "pass-en.contract.md")],
            capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
        )
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")

    def test_fail_empty_report_cell(self):
        """Report cell is `?` (never run `python -m verdict`) -> fail."""
        r = run_gate("--contract", str(FIXTURES / "fail-empty-report.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("no Report path", r.stderr)

    def test_fail_report_not_found(self):
        r = run_gate("--contract", str(FIXTURES / "fail-report-not-found.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("not found", r.stderr)

    def test_fail_malformed_json(self):
        r = run_gate("--contract", str(FIXTURES / "fail-malformed-json.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("not valid JSON", r.stderr)

    def test_fail_missing_overall_key(self):
        """A report JSON that isn't design-fidelity-gate's shape at all
        (no `overall` key) -> fail, not a silent pass."""
        r = run_gate("--contract", str(FIXTURES / "fail-missing-overall.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("overall", r.stderr)

    def test_fail_unexpected_overall_value(self):
        r = run_gate("--contract", str(FIXTURES / "fail-unexpected-overall.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("MAYBE", r.stderr)

    def test_fail_overall_fail_names_bucket(self):
        """overall=FAIL -> fail, reason names the failing bucket (`color`)
        so the reader doesn't have to reopen the JSON."""
        r = run_gate("--contract", str(FIXTURES / "fail-overall-fail.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("color", r.stderr)

    def test_fail_no_table(self):
        r = run_gate("--contract", str(FIXTURES / "fail-no-table.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_empty_file(self):
        r = run_gate("--contract", str(FIXTURES / "fail-empty-file.contract.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_missing_file(self):
        r = run_gate("--contract", "/nonexistent/x.fidelity.contract.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fidelity contract file not found", r.stderr)

    def test_fail_both_forms(self):
        """--contract together with --repo/--screen is rejected."""
        r = run_gate("--contract", "x.md", "--repo", "r", "--screen", "s")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_partial_repo_screen(self):
        r = run_gate("--repo", "r")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_neither_form(self):
        r = run_gate()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that fidelity.py imports nothing third-
        party — NO Playwright/pixelmatch/coloraide, NO subprocess (FID-01)."""
        src = GATE.read_text(encoding="utf-8")
        stdlib_ok_prefixes = ("import argparse", "import json", "import sys", "from pathlib", "from __future__")
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
        self.assertNotIn("import subprocess", src)


class FidelityGateParserUnitTests(unittest.TestCase):
    """Direct calls into fidelity.py's parsing helpers — no subprocess."""

    def test_applies_true_for_qualifying_table(self):
        text = "| Screen | Report |\n|--|--|\n| a | x.json |\n"
        self.assertTrue(fidelity_gate.applies(text))

    def test_applies_false_for_golden_record_table(self):
        """A golden-record-shaped table (Expected+Actual, no Screen/Report)
        must NOT be claimed by this gate."""
        text = "| Record | Expected | Actual |\n|--|--|--|\n| a | 1 | 1 |\n"
        self.assertFalse(fidelity_gate.applies(text))

    def test_findings_lists_every_problem_row(self):
        text = (
            "| Screen | Report |\n"
            "|--|--|\n"
            "| a |  |\n"
            "| b | /nonexistent/report.json |\n"
        )
        fs = fidelity_gate.findings(text)
        self.assertEqual(len(fs), 2)

    def test_multiple_tables_all_evaluated(self):
        """FID-05: a second table further down the SAME file, whose row
        fails, must not be skipped just because the first table passed."""
        text = fixture_text("fail-multi-table-second-fails.contract.md")
        base = FIXTURES
        ok, reason = fidelity_gate.evaluate_contract(text, base)
        self.assertFalse(ok)
        self.assertIn("screen-b", reason)

    def test_relative_report_path_resolved_against_base_dir(self):
        text = "| Screen | Report |\n|--|--|\n| a | reports/pass.report.json |\n"
        ok, _ = fidelity_gate.evaluate_contract(text, FIXTURES)
        self.assertTrue(ok)

    def test_relative_report_path_without_base_dir_uses_cwd(self):
        text = "| Screen | Report |\n|--|--|\n| a | reports/pass.report.json |\n"
        ok, reason = fidelity_gate.evaluate_contract(text, None)
        self.assertFalse(ok)
        self.assertIn("not found", reason)

    def test_perf_pathological_input_is_fast_too(self):
        text = "| Screen | Report |\n" + (("|" * 200) + ("-" * 200) + "\n") * 500
        start = time.monotonic()
        fidelity_gate.evaluate_contract(text, FIXTURES)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)

    def test_whitespace_only_text_fails(self):
        ok, _ = fidelity_gate.evaluate_contract("   \n\n\t \n", FIXTURES)
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _ = fidelity_gate.evaluate_contract("", FIXTURES)
        self.assertFalse(ok)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
