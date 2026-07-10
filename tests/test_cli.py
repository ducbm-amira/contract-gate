#!/usr/bin/env python3
"""Stdlib unittest for the contract-gate CLI (check / init / draft).

Run: cd <repo root> && python3 -m unittest tests/test_cli.py -v
"""
from __future__ import annotations

import json
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

    def test_check_skips_unowned_file_with_warning(self):
        """A *.contract.md with no data-binding table is skipped (not failed,
        exit stays 0) but F1: never silently — a per-file warning names it
        and says why it was not graded."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "other.contract.md").write_text("# just prose, no table\n", encoding="utf-8")
            r = run_cli("check", d)
            self.assertEqual(r.returncode, 0)
            self.assertIn("warn", r.stdout)
            self.assertIn("other.contract.md", r.stdout)
            self.assertIn("NOT graded", r.stdout)

    def test_check_json_format(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.contract.md").write_text(
                (FIXTURES / "pass-en.map.md").read_text(encoding="utf-8"), encoding="utf-8")
            r = run_cli("check", d, "--format", "json")
            self.assertEqual(r.returncode, 0)
            self.assertIn('"pass": true', r.stdout)
            payload = json.loads(r.stdout)
            self.assertIn("results", payload)
            self.assertIn("warnings", payload)
            self.assertEqual(payload["warnings"], [])

    def test_check_json_warnings_array(self):
        """F1: an unclaimed file shows up in the JSON 'warnings' array."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "other.contract.md").write_text("# just prose, no table\n", encoding="utf-8")
            r = run_cli("check", d, "--format", "json")
            self.assertEqual(r.returncode, 0)
            payload = json.loads(r.stdout)
            self.assertEqual(len(payload["warnings"]), 1)
            self.assertIn("other.contract.md", payload["warnings"][0])

    def test_check_explicit_file_is_graded(self):
        """F1 regression (2026-07-11): `check <file>` used to fall through
        rglob() (a file has no children), print 'no contract files found'
        and exit 0 — a FAILING contract passed at the CLI level."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "route.manifest.md"
            f.write_text(
                "| # | Behavior | Observable |\n|--|--|--|\n| 1 | x | - |\n",
                encoding="utf-8",
            )
            r = run_cli("check", str(f))
            self.assertEqual(r.returncode, 1, msg=r.stdout + r.stderr)
            self.assertIn("empty Observable", r.stdout)

    def test_check_explicit_file_unclaimed_exits_1(self):
        """F1: an explicitly named file that NO gate claims must fail loudly
        (the user pointed at it — silence would be a false pass)."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "orphan.manifest.md"
            f.write_text("# prose only, no table\n", encoding="utf-8")
            r = run_cli("check", str(f))
            self.assertEqual(r.returncode, 1)
            self.assertIn("no gate claims this file", r.stdout)

    def test_check_undecodable_file_is_blocked_exit_2(self):
        """F8 regression (2026-07-11): a non-UTF-8 file matching a glob used
        to crash the whole run with a traceback (aborting every not-yet-
        graded file, emitting no JSON). It is now a BLOCKED result: exit 2,
        JSON still emitted, sibling contracts still graded."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "broken.spec.md").write_bytes(b"\x93\xfa\x96\x7b\x8c\xea | Observable |")
            (Path(d) / "route.manifest.md").write_text(
                "| # | Behavior | Observable |\n|--|--|--|\n| 1 | x | dom check |\n",
                encoding="utf-8",
            )
            r = run_cli("check", d, "--format", "json")
            self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)
            payload = json.loads(r.stdout)  # JSON must still be valid
            blocked = [x for x in payload["results"] if x["blocked"]]
            graded = [x for x in payload["results"] if x["pass"]]
            self.assertEqual(len(blocked), 1)
            self.assertIn("broken.spec.md", blocked[0]["file"])
            # the healthy sibling manifest was still graded, not aborted
            self.assertTrue(any("route.manifest.md" in x["file"] for x in graded))

    def test_check_missing_path_exits_2(self):
        """A nonexistent path is a tool-usage error (BLOCKED), not a
        contract gap."""
        r = run_cli("check", "/nonexistent/dir-xyz")
        self.assertEqual(r.returncode, 2)
        self.assertIn("path not found", r.stderr)


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
    def test_init_scaffolds_discoverable_and_fail_until_filled(self):
        """F9 (2026-07-11, reverses the old 'scaffold checks clean' test):
        init used to write example.<key>.contract.md for all six gates while
        only data-binding's GLOBS matched *.contract.md — 5 of 6 scaffolds
        were invisible to `check`, and the one discovered scaffold PASSED
        with placeholder content. Scaffold names now follow each gate's own
        GLOBS, every scaffold is discovered, and every scaffold FAILS until
        filled (an unfilled contract is a todo, not a pass)."""
        with tempfile.TemporaryDirectory() as d:
            r = run_cli("init", d)
            self.assertEqual(r.returncode, 0)
            expected_names = {
                "example.data-binding.md", "example.greenfield.md",
                "example.manifest.md", "example.golden-record.md",
                "example.fidelity.md", "example.testgen.md",
            }
            self.assertEqual(
                {p.name for p in Path(d).iterdir()}, expected_names
            )
            r2 = run_cli("check", d, "--format", "json")
            self.assertEqual(r2.returncode, 1, msg=r2.stdout)
            payload = json.loads(r2.stdout)
            # every scaffold discovered (no warnings), every scaffold failing
            self.assertEqual(payload["warnings"], [])
            graded_gates = {x["gate"] for x in payload["results"]}
            self.assertEqual(
                graded_gates,
                {"data-binding", "greenfield", "manifest", "golden-record", "fidelity", "testgen"},
            )
            self.assertTrue(all(not x["pass"] for x in payload["results"]),
                            msg=f"a placeholder scaffold passed: {payload['results']}")


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
