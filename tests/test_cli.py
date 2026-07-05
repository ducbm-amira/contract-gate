#!/usr/bin/env python3
"""Stdlib unittest for the contract-gate CLI (check / init / draft).

Run: cd <repo root> && python3 -m unittest tests/test_cli.py -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "data_binding"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "contract_gate.cli", *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
    )


class CheckTests(unittest.TestCase):
    def test_check_passing_contract_exit0(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.contract.md").write_text(
                (FIXTURES / "pass-en.map.md").read_text(encoding="utf-8"), encoding="utf-8")
            r = run_cli("check", d)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("pass", r.stdout)

    def test_check_failing_contract_exit1(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.contract.md").write_text(
                (FIXTURES / "fail-empty-source.map.md").read_text(encoding="utf-8"), encoding="utf-8")
            r = run_cli("check", d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("fail", r.stdout)

    def test_check_skips_unowned_file(self):
        """A *.contract.md with no data-binding table is skipped, not failed."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "other.contract.md").write_text("# just prose, no table\n", encoding="utf-8")
            r = run_cli("check", d)
            self.assertEqual(r.returncode, 0)
            self.assertIn("no contract files found", r.stdout)

    def test_check_json_format(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.contract.md").write_text(
                (FIXTURES / "pass-en.map.md").read_text(encoding="utf-8"), encoding="utf-8")
            r = run_cli("check", d, "--format", "json")
            self.assertEqual(r.returncode, 0)
            self.assertIn('"pass": true', r.stdout)


class CheckAllTests(unittest.TestCase):
    _TWO_GAPS = (
        "# map\n\n"
        "| Screen | Element | Type | Source | Null |\n"
        "|--|--|--|--|--|\n"
        "| s | a | data |  | hide |\n"
        "| s | b | data | ? not in spec | hide |\n"
    )

    def test_default_reports_first_only(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.contract.md").write_text(self._TWO_GAPS, encoding="utf-8")
            r = run_cli("check", d)
            self.assertEqual(r.returncode, 1)
            # default stops at the first finding per file
            self.assertEqual(r.stdout.count("has no source"), 1)

    def test_all_lists_every_finding(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.contract.md").write_text(self._TWO_GAPS, encoding="utf-8")
            r = run_cli("check", d, "--all")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout.count("has no source"), 2)
            self.assertIn('"s × a"', r.stdout)
            self.assertIn('"s × b"', r.stdout)
            # summary counts by distinct contract file, not by finding
            self.assertIn("across 1 contract(s)", r.stdout)

    def test_all_still_passes_clean_contract(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.contract.md").write_text(
                (FIXTURES / "pass-en.map.md").read_text(encoding="utf-8"), encoding="utf-8")
            r = run_cli("check", d, "--all")
            self.assertEqual(r.returncode, 0)
            self.assertIn("pass", r.stdout)


class InitTests(unittest.TestCase):
    def test_init_scaffolds_and_checks_clean(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_cli("init", d)
            self.assertEqual(r.returncode, 0)
            self.assertTrue((Path(d) / "example.data-binding.contract.md").exists())
            # the scaffold must itself pass the gate (a friendly starting point)
            r2 = run_cli("check", d)
            self.assertEqual(r2.returncode, 0, msg=r2.stdout)


class DraftTests(unittest.TestCase):
    def test_draft_prompt_has_template_and_antigaming(self):
        r = run_cli("draft", "--gate", "data-binding")
        self.assertEqual(r.returncode, 0)
        self.assertIn("CONTRACT TEMPLATE", r.stdout)
        self.assertIn("do NOT game", r.stdout)
        self.assertIn("data-binding:start", r.stdout)

    def test_draft_unknown_gate_exit1(self):
        r = run_cli("draft", "--gate", "does-not-exist")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown gate", r.stderr)

    def test_draft_via_writes_contract_then_gate_runs(self):
        """--via pipes to a command; simulate an LLM returning a good contract
        with `cat <goodfile>` (ignores stdin), then gate the result."""
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.contract.md"
            good = FIXTURES / "pass-en.map.md"
            r = run_cli("draft", "--gate", "data-binding", "--via", f"cat {good}", "--out", str(out))
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            self.assertTrue(out.exists())
            r2 = run_cli("check", d)
            self.assertEqual(r2.returncode, 0, msg=r2.stdout)


if __name__ == "__main__":
    unittest.main()
