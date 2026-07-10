#!/usr/bin/env python3
"""Stdlib unittest for port-harness/greenfield_gate.py (GREEN-01, plan 05-01).

Mirrors manifest_gate_test.py 1:1 (subprocess harness, case matrix,
stdlib-import test, perf/ReDoS guard) plus the greenfield-specific
two-column, resolvable-path, and visual-exempt cases (D-02/D-03/D-04).

Run: cd <repo root> && python3 -m unittest port-harness/greenfield_gate_test.py -v
"""
from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "greenfield.py"
FIXTURES = TESTS_DIR / "fixtures" / "greenfield"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import greenfield as greenfield_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class GreenfieldGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 greenfield_gate.py ...`
    entrypoint, matching the plan's acceptance_criteria commands 1:1."""

    def test_pass_vn_forgiving(self):
        """VN headers; both Design-ref and Observable cells carry extra
        whitespace, VN prose, and full-width punctuation (D-01) -> pass."""
        r = run_gate("--spec", str(FIXTURES / "pass-vn.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_en_header_variant(self):
        """EN header variant (Behavior/Design-ref/target/Observable) -> pass (D-01)."""
        r = run_gate("--spec", str(FIXTURES / "pass-en.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_reordered_columns(self):
        """Observable and Design-ref columns NOT in canonical order -> still
        pass (column-reorder tolerance, D-01)."""
        r = run_gate("--spec", str(FIXTURES / "pass-reordered.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_designref_link_not_curled(self):
        """A `.../design/h/<code>` Design-ref link passes on format alone --
        the run completes fast/offline, proving no network call was made
        (D-03, no-network preserved)."""
        start = time.monotonic()
        r = run_gate("--spec", str(FIXTURES / "pass-link-designref.spec.md"))
        elapsed = time.monotonic() - start
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)
        self.assertLess(elapsed, 2.0, msg="took too long -- suspect a network call was attempted")

    def test_pass_local_designref(self):
        """A Design-ref pointing at a sibling fixture file that exists on
        disk resolves and passes (D-03 local-path resolvable)."""
        r = run_gate("--spec", str(FIXTURES / "pass-local-designref.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_no_visual_exempt_flag(self):
        """`visual: none` header exempts the Design-ref layer for every row;
        Observable stays mandatory and is populated -> pass (D-04)."""
        r = run_gate("--spec", str(FIXTURES / "pass-no-visual-exempt.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_empty_observable_names_row(self):
        """A row has an empty Observable cell even though Design-ref is
        valid -> exit!=0, stderr says fail + names the offending row."""
        r = run_gate("--spec", str(FIXTURES / "fail-empty-observable.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_fail_empty_designref_names_row(self):
        """Non-exempt spec, a row has an empty Design-ref cell -> exit!=0,
        stderr says fail + names the offending row (D-04: blank is never
        treated as an implicit exempt)."""
        r = run_gate("--spec", str(FIXTURES / "fail-empty-designref.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_fail_designref_missing_path(self):
        """A local Design-ref path that does not exist on disk -> exit!=0 (D-03)."""
        r = run_gate("--spec", str(FIXTURES / "fail-designref-missing-path.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_fail_empty_file(self):
        """File exists but is empty/whitespace -> exit!=0."""
        r = run_gate("--spec", str(FIXTURES / "fail-empty-file.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_no_table(self):
        """Non-empty file, no recognizable behavior table -> exit!=0."""
        r = run_gate("--spec", str(FIXTURES / "fail-no-table.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_pass_confidence_green_empty_restated_ok(self):
        """D-06: Confidence column present, every row 🟢 -> Restated may
        stay empty, still passes."""
        r = run_gate("--spec", str(FIXTURES / "pass-confidence-green-empty-restated.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_pass_confidence_yellow_with_restated(self):
        """D-06: a 🟡 row with a genuine (non-copied) Restated cell passes."""
        r = run_gate("--spec", str(FIXTURES / "pass-confidence-yellow-with-restated.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_confidence_yellow_empty_restated(self):
        """D-06: a 🟡/🔴 row with a blank Restated cell -> exit!=0, names
        the offending row."""
        r = run_gate("--spec", str(FIXTURES / "fail-confidence-yellow-empty-restated.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Restated", r.stderr)

    def test_fail_restated_copied_from_observable(self):
        """D-06: a Restated cell that's a verbatim copy of Design-ref/
        Observable does not count as the human's own words -> exit!=0."""
        r = run_gate("--spec", str(FIXTURES / "fail-restated-copied.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("copy", r.stderr)

    def test_fail_confidence_column_without_restated_column(self):
        """D-06: a Confidence column with no Restated/Human column anywhere
        is a schema error, rejected before any row is inspected."""
        r = run_gate("--spec", str(FIXTURES / "fail-confidence-column-no-restated-column.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("D-06", r.stderr)

    def test_fail_empty_confidence(self):
        """D-06: Confidence column present but a row's Confidence cell is
        blank -> exit!=0."""
        r = run_gate("--spec", str(FIXTURES / "fail-empty-confidence.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Confidence", r.stderr)

    def test_pass_multi_table_master_spec(self):
        """D-07: a master spec with 2 screen-sections, each its own table,
        both valid -> pass, counting rows from BOTH tables."""
        r = run_gate("--spec", str(FIXTURES / "pass-multi-table-master-spec.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)
        self.assertIn("2 behavior row(s) verified across 2 table(s)", r.stdout)

    def test_fail_multi_table_violation_in_later_table_not_missed(self):
        """D-07 regression guard: a violation in the SECOND/THIRD table of a
        multi-table master spec must fail the gate (not be silently skipped
        because table 1 already passed) -- names the screen heading."""
        r = run_gate("--spec", str(FIXTURES / "fail-multi-table-second-table-violation.spec.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("Màn 2", r.stderr)

    def test_findings_all_report_every_table_not_just_first(self):
        """D-07 + `--all`: findings() must surface violations from EVERY
        table, not stop after the first table's rows are exhausted."""
        text = Path(FIXTURES / "fail-multi-table-second-table-violation.spec.md").read_text(encoding="utf-8")
        out = greenfield_gate.findings(text, FIXTURES / "fail-multi-table-second-table-violation.spec.md")
        self.assertEqual(len(out), 2, msg=f"expected 2 findings (one per bad table), got: {out}")
        self.assertTrue(any("Màn 2" in f for f in out), msg=out)
        self.assertTrue(any("Màn 3" in f for f in out), msg=out)

    def test_pass_no_confidence_column_is_unaffected(self):
        """Backward compatibility: specs with no Confidence column at all
        are graded exactly as before D-06 (already covered by the other
        pass-* fixtures above, asserted again here for clarity)."""
        r = run_gate("--spec", str(FIXTURES / "pass-en.spec.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")

    def test_fail_missing_file(self):
        """Path does not exist -> exit!=0, reason 'spec not found'.
        No fixture -- exercised with a nonexistent path per the plan."""
        r = run_gate("--spec", "/nonexistent/x.spec.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("spec not found", r.stderr)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that greenfield_gate.py imports nothing
        third-party (D-05) -- redundant with the shell acceptance check but
        keeps the prohibition enforced in the test suite itself."""
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


class GreenfieldGateParserUnitTests(unittest.TestCase):
    """Exercise evaluate_spec() directly (no subprocess) -- fast, precise,
    used for the perf/ReDoS guard and small parser edge cases."""

    def test_perf_large_input_is_linear_and_fast(self):
        header = "| # | Behavior | Design-ref | target | Observable |\n"
        sep = "|---|---|---|---|---|\n"
        rows = "".join(
            f"| {i} | behavior {i} | N/A-logic | logic | value {i} |\n" for i in range(5000)
        )
        # visual: none header exempts Design-ref so the perf run never touches
        # the filesystem per row -- isolates the parser's linear-time claim.
        text = "---\ntask: perf\nvisual: none\n---\n\n" + header + sep + rows
        start = time.monotonic()
        ok, reason = greenfield_gate.evaluate_spec(text)
        elapsed = time.monotonic() - start
        self.assertTrue(ok, msg=reason)
        self.assertLess(elapsed, 1.0, msg=f"parse took {elapsed:.3f}s -- not linear?")

    def test_perf_pathological_input_is_fast_too(self):
        """Adversarial pipes/dashes that would blow up a catastrophic-backtracking
        regex; a linear parser must still finish comfortably under 1s (T-02-01)."""
        text = "| Design-ref | Observable |\n" + (("|" * 200) + ("-" * 200) + "\n") * 500
        start = time.monotonic()
        greenfield_gate.evaluate_spec(text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)

    def test_whitespace_only_text_fails(self):
        ok, _reason = greenfield_gate.evaluate_spec("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _reason = greenfield_gate.evaluate_spec("")
        self.assertFalse(ok)

    def test_fail_placeholder_observable(self):
        """F2 regression (2026-07-11): an Observable of `?`/`TODO: ...` is an
        UNFILLED cell — both used to PASS (false PASS) because this gate only
        checked dash look-alikes before adopting the shared empty-cell rule."""
        for bad in ("?", "TODO", "TODO: write assertion", "? not sure"):
            text = (
                "| # | Behavior | Design-ref | Observable |\n"
                "|--|--|--|--|\n"
                f"| 1 | b | https://claude.ai/design/h/abc | {bad} |\n"
            )
            ok, reason = greenfield_gate.evaluate_spec(text)
            self.assertFalse(ok, msg=f"placeholder {bad!r} passed: {reason}")
            self.assertIn("empty Observable", reason)

    def test_fail_placeholder_restated(self):
        """F2/D-06 regression: a non-🟢 row whose Restated cell is `?` used
        to pass D-06 — a `?` rubber-stamp defeats the cognitive-forcing
        function D-06 exists for."""
        text = (
            "| # | Behavior | Design-ref | Observable | Confidence | Restated |\n"
            "|--|--|--|--|--|--|\n"
            "| 1 | b | https://claude.ai/design/h/abc | cell shows X | 🟡 | ? |\n"
        )
        ok, reason = greenfield_gate.evaluate_spec(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("empty Restated", reason)

    def test_fail_design_observable_needle_collision(self):
        """F3 regression (GOLD-06 class, 2026-07-11): a single header cell
        matching BOTH needle sets ("Design & Observable assertion") used to
        resolve Design-ref and Observable to the SAME column — one filled
        cell satisfied both oracle layers (false PASS). With the exclusion
        guard such a table no longer qualifies -> loud 'no behavior table'."""
        text = (
            "| # | Behavior | Design & Observable assertion |\n"
            "|--|--|--|\n"
            "| 1 | b | https://claude.ai/design/h/abc |\n"
        )
        self.assertFalse(greenfield_gate.applies(text))
        ok, reason = greenfield_gate.evaluate_spec(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("no behavior table", reason)

    def test_fail_abutting_table_graded_with_own_columns(self):
        """F4 regression: a second qualifying table glued directly under the
        first (no blank line), with a different column order, must be graded
        under its OWN columns — its violations used to be invisible or
        misattributed."""
        text = (
            "| # | Behavior | Design-ref | Observable |\n"
            "|--|--|--|--|\n"
            "| 1 | x | https://claude.ai/design/h/a | dom check |\n"
            "| # | Observable | Design-ref | Behavior |\n"
            "|--|--|--|--|\n"
            "| 2 | - | https://claude.ai/design/h/b | click y |\n"
        )
        ok, reason = greenfield_gate.evaluate_spec(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("empty Observable", reason)

    def test_fail_header_only_table(self):
        """F7: a header-only qualifying table (0 rows) fails, naming it."""
        text = (
            "| # | Behavior | Design-ref | Observable |\n"
            "|--|--|--|--|\n"
        )
        ok, reason = greenfield_gate.evaluate_spec(text)
        self.assertFalse(ok, msg=reason)
        self.assertIn("no rows", reason)


if __name__ == "__main__":
    unittest.main()
