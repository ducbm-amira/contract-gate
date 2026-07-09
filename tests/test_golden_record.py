#!/usr/bin/env python3
"""Stdlib unittest for contract_gate/gates/golden_record.py (GOLD-01, gate #4).

Mirrors test_data_binding.py 1:1 (subprocess CLI harness, case matrix,
stdlib-import test, perf/ReDoS guard) plus the golden-record-specific cases:
Expected/Actual presence, exact-match comparison (the whole point of this
gate — data-CORRECTNESS, not just declared-source), the optional Edge-case
column, and the delimiter scope.

Run: cd <repo root> && python3 -m unittest tests/test_golden_record.py -v
"""
from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "golden_record.py"
FIXTURES = TESTS_DIR / "fixtures" / "golden_record"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import golden_record as golden_record_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class GoldenRecordGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 golden_record.py ...`."""

    def test_pass_vn_matching(self):
        """VN headers; happy-path + null-edge-case rows where Expected ==
        Actual (both written as the correctly-rendered display string) ->
        pass (GOLD-02/03)."""
        r = run_gate("--map", str(FIXTURES / "pass-vn.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_en_no_edgecase_column(self):
        """EN headers, no optional Edge-case column at all -> still pass
        (Edge-case is optional-to-track, like data_binding's format column)."""
        r = run_gate("--map", str(FIXTURES / "pass-en.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_reordered_columns(self):
        """Actual/Edge/Expected/Field NOT in canonical order -> still pass
        (column-reorder tolerance, GOLD-02)."""
        r = run_gate("--map", str(FIXTURES / "pass-reordered.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_delimiter_restricts_scope(self):
        """A mismatched Expected/Actual row OUTSIDE the
        <!-- golden-record --> block is ignored; only the matching row
        inside is evaluated -> pass (GOLD-02)."""
        r = run_gate("--map", str(FIXTURES / "pass-delimiter-block.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_empty_expected(self):
        """A row with a blank Expected -> exit!=0 (never pinned a real
        answer, contract is still just a hypothesis, DP4)."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-expected.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Expected", r.stderr)

    def test_fail_empty_actual(self):
        """A row with a blank Actual -> exit!=0 (nobody has looked at the
        real running app yet for this record)."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-actual.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Actual", r.stderr)

    def test_fail_mismatch_names_both_values(self):
        """Expected and Actual are both filled but disagree -> exit!=0,
        reason names BOTH values (this is the core data-correctness catch)."""
        r = run_gate("--map", str(FIXTURES / "fail-mismatch.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("3LDK", r.stderr)
        self.assertIn("2LDK", r.stderr)

    def test_fail_empty_edgecase_cell(self):
        """Edge-case column present but a row leaves it blank -> fail
        (GOLD-03.4, mirrors data_binding's optional-format-column rule)."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-edgecase.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("edge-case", r.stderr)

    def test_fail_placeholder_expected(self):
        """A bare `?` placeholder Expected is UNFILLED -> fail (GOLD-03.1)."""
        r = run_gate("--map", str(FIXTURES / "fail-placeholder-expected.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_annotated_question_expected(self):
        """A leading `?` with an explanatory reason is still unresolved ->
        fail. Guards the hole an agent hits when it annotates a blind spot
        instead of writing a bare `?`."""
        r = run_gate("--map", str(FIXTURES / "fail-annotated-question-expected.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Expected", r.stderr)

    def test_fail_no_table(self):
        """No table with both Expected and Actual columns -> fail (GOLD-02)."""
        r = run_gate("--map", str(FIXTURES / "fail-no-table.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_empty_file(self):
        """File exists but is whitespace-only -> fail."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-file.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_missing_file(self):
        """Path does not exist -> exit!=0, reason names the missing file."""
        r = run_gate("--map", "/nonexistent/x.map.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("golden-record file not found", r.stderr)

    def test_fail_both_forms(self):
        """--map together with --repo/--task is rejected."""
        r = run_gate("--map", "x.md", "--repo", "r", "--task", "t")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that golden_record.py imports nothing
        third-party — NO DB driver, NO network client (GOLD-01)."""
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

    def test_pass_header_needle_collision_with_real_match(self):
        """GOLD-06 regression: Expected's own header text contains "hiển
        thị" (an ACTUAL_NEEDLES entry) -> actual_col must resolve to the
        REAL Actual column, not fall back onto Expected's own column."""
        r = run_gate("--map", str(FIXTURES / "pass-header-collision.map.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_header_needle_collision_with_real_mismatch(self):
        """GOLD-06 regression: same tricky header, but Expected != Actual for
        real -> must FAIL naming both real values. Before the fix this
        silently PASSED (actual_col pointed back at Expected, comparing it
        to itself)."""
        r = run_gate("--map", str(FIXTURES / "fail-header-collision-mismatch.map.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("29,880,000", r.stderr)
        self.assertIn("30,000,000", r.stderr)

    def test_globs_do_not_match_init_scaffold_filename(self):
        """GOLD-07 regression: contract-gate init writes
        example.golden-record.contract.md — GLOBS must NOT match it (would
        make the gate self-discover its own no-real-report-yet scaffold and
        self-fail), mirroring manifest.py/greenfield.py's narrow GLOBS."""
        import fnmatch
        scaffold_name = "example.golden-record.contract.md"
        for pattern in golden_record_gate.GLOBS:
            self.assertFalse(
                fnmatch.fnmatch(scaffold_name, pattern),
                msg=f"GLOBS pattern {pattern!r} matches the init scaffold filename",
            )

    def test_template_itself_is_not_a_silent_false_pass(self):
        """GOLD-06 regression: TEMPLATE's own Expected/Actual placeholder
        cells are deliberately DIFFERENT text (an unfilled scaffold, not a
        real match) -> evaluate_map(TEMPLATE) must report a real mismatch,
        not a false pass from the header-needle collision."""
        ok, reason = golden_record_gate.evaluate_map(golden_record_gate.TEMPLATE)
        self.assertFalse(ok)
        self.assertIn("expected", reason)
        self.assertIn("actual", reason)


class GoldenRecordGateParserUnitTests(unittest.TestCase):
    """Exercise evaluate_map() directly -- fast, precise, perf/ReDoS guard."""

    def test_multiple_tables_all_evaluated(self):
        """Two per-screen tables; a mismatch in the SECOND table is still
        caught (GOLD-02 scans every qualifying table)."""
        text = (
            "| Record | Field | Expected | Actual |\n"
            "|--|--|--|--|\n"
            "| a | x | 1 | 1 |\n"
            "\nsome prose\n\n"
            "| Record | Field | Expected | Actual |\n"
            "|--|--|--|--|\n"
            "| b | y | 2 | 3 |\n"
        )
        ok, reason = golden_record_gate.evaluate_map(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("y", reason)

    def test_exact_match_after_strip_passes(self):
        """Surrounding whitespace in either cell is stripped before compare."""
        text = (
            "| Record | Field | Expected | Actual |\n"
            "|--|--|--|--|\n"
            "|  a  |  x  |   ¥100   | ¥100 |\n"
        )
        ok, reason = golden_record_gate.evaluate_map(text)
        self.assertTrue(ok, msg=reason)

    def test_zero_qualifying_rows_impossible_but_no_table_fails(self):
        """A table with headers only (no body rows) still yields a pass
        summary of 0 records — nothing to contradict, but also nothing
        proven; documented as current behavior (an empty table is not the
        same failure as a missing table)."""
        text = "| Record | Field | Expected | Actual |\n|--|--|--|--|\n"
        ok, reason = golden_record_gate.evaluate_map(text)
        self.assertTrue(ok, msg=reason)
        self.assertIn("0 golden record", reason)

    def test_perf_large_input_is_linear_and_fast(self):
        header = "| Record | Field | Expected | Actual |\n"
        sep = "|--|--|--|--|\n"
        rows = "".join(f"| r{i} | f | v{i} | v{i} |\n" for i in range(5000))
        text = header + sep + rows
        start = time.monotonic()
        ok, reason = golden_record_gate.evaluate_map(text)
        elapsed = time.monotonic() - start
        self.assertTrue(ok, msg=reason)
        self.assertLess(elapsed, 1.0, msg=f"parse took {elapsed:.3f}s -- not linear?")

    def test_perf_pathological_input_is_fast_too(self):
        text = "| Expected | Actual |\n" + (("|" * 200) + ("-" * 200) + "\n") * 500
        start = time.monotonic()
        golden_record_gate.evaluate_map(text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)

    def test_whitespace_only_text_fails(self):
        ok, _ = golden_record_gate.evaluate_map("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _ = golden_record_gate.evaluate_map("")
        self.assertFalse(ok)

    def test_applies_true_for_qualifying_table(self):
        text = "| Record | Expected | Actual |\n|--|--|--|\n| a | 1 | 1 |\n"
        self.assertTrue(golden_record_gate.applies(text))

    def test_applies_false_for_data_binding_table(self):
        """A data-binding-shaped table (type+source, no Expected/Actual)
        must NOT be claimed by this gate — a gate never judges a file it
        does not own."""
        text = "| Element | Type | Source | Null |\n|--|--|--|--|\n| x | data | `a.x` | hide |\n"
        self.assertFalse(golden_record_gate.applies(text))

    def test_findings_lists_every_problem_row(self):
        text = (
            "| Record | Field | Expected | Actual |\n"
            "|--|--|--|--|\n"
            "| a | x |  | 1 |\n"
            "| b | y | 2 |  |\n"
            "| c | z | 3 | 4 |\n"
        )
        fs = golden_record_gate.findings(text)
        self.assertEqual(len(fs), 3)


if __name__ == "__main__":
    unittest.main()
