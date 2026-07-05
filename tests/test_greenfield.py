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


if __name__ == "__main__":
    unittest.main()
