#!/usr/bin/env python3
"""Stdlib unittest for contract_gate/gates/testgen.py (RTM-01, gate #6).

Mirrors test_fidelity.py / test_golden_record.py (subprocess CLI harness,
case matrix, stdlib-import test, perf/ReDoS guard) plus the RTM-specific
cases: Requirement/Expected presence, the optional Technique column, the
delimiter scope, and multi-table scanning.

Run: cd <repo root> && python3 -m unittest tests/test_testgen.py -v
"""
from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "testgen.py"
FIXTURES = TESTS_DIR / "fixtures" / "testgen"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import testgen as testgen_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestgenGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 testgen.py ...`."""

    def test_pass_en(self):
        r = run_gate("--rtm", str(FIXTURES / "pass-en.rtm.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_vn_headers(self):
        r = run_gate("--rtm", str(FIXTURES / "pass-vn.rtm.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_with_technique_column_filled(self):
        r = run_gate("--rtm", str(FIXTURES / "pass-with-technique.rtm.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_reordered_columns(self):
        r = run_gate("--rtm", str(FIXTURES / "pass-reordered.rtm.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_delimiter_restricts_scope(self):
        r = run_gate("--rtm", str(FIXTURES / "pass-delimiter-block.rtm.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_empty_requirement(self):
        """A row with no Requirement/Behavior ref -> fail (RTM-03.1)."""
        r = run_gate("--rtm", str(FIXTURES / "fail-empty-req.rtm.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Requirement/Behavior reference", r.stderr)

    def test_fail_empty_expected(self):
        """A row with no Expected/Oracle -> fail (RTM-03.2)."""
        r = run_gate("--rtm", str(FIXTURES / "fail-empty-expected.rtm.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Expected/Oracle", r.stderr)

    def test_fail_placeholder_expected(self):
        """A bare `?` Expected is UNFILLED -> fail (same as an empty cell,
        the whole point being it forces resolution before the gate passes)."""
        r = run_gate("--rtm", str(FIXTURES / "fail-placeholder-expected.rtm.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_empty_technique_when_column_present(self):
        r = run_gate("--rtm", str(FIXTURES / "fail-empty-technique.rtm.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Technique", r.stderr)

    def test_fail_no_table(self):
        r = run_gate("--rtm", str(FIXTURES / "fail-no-table.rtm.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_empty_file(self):
        r = run_gate("--rtm", str(FIXTURES / "fail-empty-file.rtm.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_missing_file(self):
        r = run_gate("--rtm", "/nonexistent/x.testgen.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("RTM file not found", r.stderr)

    def test_fail_both_forms(self):
        r = run_gate("--rtm", "x.md", "--repo", "r", "--task", "t")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_partial_repo_task(self):
        r = run_gate("--repo", "r")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_neither_form(self):
        r = run_gate()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that testgen.py imports nothing third-
        party — NO LLM client, NO network (RTM-01)."""
        src = GATE.read_text(encoding="utf-8")
        stdlib_ok_prefixes = ("import argparse", "import sys", "from pathlib", "from __future__", "from .. import tableparse", "from contract_gate import tableparse")
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


class TestgenGateParserUnitTests(unittest.TestCase):
    """Direct calls into testgen.py's parsing helpers — no subprocess."""

    def test_applies_true_for_qualifying_table(self):
        text = "| Requirement | Expected |\n|--|--|\n| a | 1 |\n"
        self.assertTrue(testgen_gate.applies(text))

    def test_applies_false_for_fidelity_table(self):
        """A fidelity-shaped table (Screen+Report, no Requirement/Expected)
        must NOT be claimed by this gate."""
        text = "| Screen | Report |\n|--|--|\n| a | x.json |\n"
        self.assertFalse(testgen_gate.applies(text))

    def test_findings_lists_every_problem_row(self):
        text = (
            "| Requirement | Expected |\n"
            "|--|--|\n"
            "| a |  |\n"
            "|  | 1 |\n"
        )
        fs = testgen_gate.findings(text)
        self.assertEqual(len(fs), 2)

    def test_multiple_tables_all_evaluated(self):
        """RTM-04: a second table further down the SAME file, whose row
        fails, must not be skipped just because the first table passed."""
        text = (FIXTURES / "fail-multi-table-second-fails.rtm.md").read_text(encoding="utf-8")
        ok, reason = testgen_gate.evaluate_rtm(text)
        self.assertFalse(ok)
        self.assertIn("REQ-B", reason)

    def test_perf_pathological_input_is_fast_too(self):
        text = "| Requirement | Expected |\n" + (("|" * 200) + ("-" * 200) + "\n") * 500
        start = time.monotonic()
        testgen_gate.evaluate_rtm(text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)

    def test_whitespace_only_text_fails(self):
        ok, _ = testgen_gate.evaluate_rtm("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _ = testgen_gate.evaluate_rtm("")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
