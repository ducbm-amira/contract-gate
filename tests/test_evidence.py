#!/usr/bin/env python3
"""Stdlib unittest for contract_gate/gates/evidence.py (EVID-01, D-05).

Ported from port-harness/evidence_gate_test.py into the repo's subprocess-harness
style (GATE points at contract_gate/gates/evidence.py; evaluate_evidence imported
from the package). Subprocess CLI harness + direct evaluate_evidence() unit tests,
stdlib-import guard, ReDoS perf guards. Fixtures are inline strings written to a
tmp file (the two report tables it parses are small and easiest to read inline).

Run: cd <repo root> && python3 -m unittest tests.test_evidence -v
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
GATE = REPO_ROOT / "contract_gate" / "gates" / "evidence.py"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import evidence as evidence_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


# ---- inline REPORT.md fixtures ----

FULL_REPORT = """
## Kịch bản đã verify

| TC-ID | Kịch bản | Kết quả | Method | Screenshot | Note |
|-------|----------|---------|--------|------------|------|
| TC-A01a | Ca phân biệt: click nut Save | ✅ PASS | UI click | ss-01-save.png | Confirmed fix có effect |
| TC-E01 | Persistence sau reload | ✅ PASS-WEAK | API only | — | Pivot do selector kẹt |
| TC-D01 | Edge case | ❌ FAIL | UI click | ss-03.png | Bug X |

## Manifest Trace

| Manifest Row # | Hành vi (từ manifest) | TC-ID | Verdict | Evidence |
|----------------|------------------------|-------|---------|----------|
| 3 | Click Save cập nhật DB | TC-C02 | ✅ PASS | ss-04-....png |
| 7 (invisible) | Tracking call | TC-E03 | ✅ PASS | network log: POST /api/track 200 |
"""

MISSING_METHOD = """
## Kịch bản đã verify

| TC-ID | Kịch bản | Kết quả | Method | Screenshot | Note |
|-------|----------|---------|--------|------------|------|
| TC-A01a | Ca phân biệt: click nut Save |  ✅ PASS |  | ss-01-save.png |  |
"""

MISSING_EVIDENCE_BOTH = """
## Kịch bản đã verify

| TC-ID | Kịch bản | Kết quả | Method | Screenshot | Note |
|-------|----------|---------|--------|------------|------|
| TC-A01a | Ca phân biệt: click nut Save | ✅ PASS | UI click |  |  |
"""

MANIFEST_TRACE_MISSING_EVIDENCE = """
## Manifest Trace

| Manifest Row # | Hành vi (từ manifest) | TC-ID | Verdict | Evidence |
|----------------|------------------------|-------|---------|----------|
| 3 | Click Save cập nhật DB | TC-C02 | ✅ PASS |  |
"""

EXEMPT_NONPASS = """
## Kịch bản đã verify

| TC-ID | Kịch bản | Kết quả | Method | Screenshot | Note |
|-------|----------|---------|--------|------------|------|
| TC-D01 | Edge case 1 | ❌ FAIL |  |  |  |
| TC-D02 | Edge case 2 | NOT-verified |  |  |  |
| TC-D03 | Edge case 3 | BLOCKED |  |  |  |
"""

FAIL_CLOSED_NO_TABLE = """
## Kịch bản đã verify (report bị đổi header, mất Method/Evidence)

| TC-ID | Kịch bản | Kết quả |
|-------|----------|---------|
| TC-A01a | Ca phân biệt: click nut Save | ✅ PASS |
"""

VN_REORDERED = """
## Kịch bản đã verify

| Kết quả | Ghi chú | TC-ID | Kịch bản | Screenshot | Method |
|---------|---------|--------|----------|------------|--------|
| ✅ PASS | Xem thêm | TC-X01 | Kịch bản X | ss-x.png | UI click |
"""

EMPTY_REPORT = "   \n\n\t \n"


def _write_tmp_report(text: str) -> Path:
    fd, raw_path = tempfile.mkstemp(suffix=".REPORT.md")
    with open(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return Path(raw_path)


class EvidenceGateCLITests(unittest.TestCase):
    """CLI-level cases — exercise the real `python3 evidence.py ...` entrypoint."""

    def _run(self, text: str) -> subprocess.CompletedProcess:
        p = _write_tmp_report(text)
        self.addCleanup(lambda: p.unlink(missing_ok=True))
        return run_gate("--report", str(p))

    def test_pass_full_report(self):
        """Every ✅/PASS row in both tables has Method + Evidence -> pass."""
        r = self._run(FULL_REPORT)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_missing_method_names_row(self):
        """'Kịch bản đã verify' ✅ row with empty Method -> fail, names the row."""
        r = self._run(MISSING_METHOD)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_fail_missing_evidence_both_empty(self):
        """✅ row with empty Screenshot AND empty Note (no evidence) -> fail."""
        r = self._run(MISSING_EVIDENCE_BOTH)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_fail_manifest_trace_missing_evidence(self):
        """'Manifest Trace' ✅/PASS row with empty Evidence cell -> fail (no
        Method column in this table -- check Evidence only)."""
        r = self._run(MANIFEST_TRACE_MISSING_EVIDENCE)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_pass_exempt_nonpass_rows(self):
        """❌ FAIL / NOT-verified / BLOCKED rows with no evidence -> pass
        (exempt: only ✅/PASS rows are subject to the check)."""
        r = self._run(EXEMPT_NONPASS)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_closed_no_gradeable_table(self):
        """Report has ✅ rows but no resolvable Method/Evidence columns
        anywhere -> fail-closed, never a vacuous pass."""
        r = self._run(FAIL_CLOSED_NO_TABLE)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertRegex(r.stderr, r"row \d+")

    def test_pass_vn_reordered_columns(self):
        """VN headers / reordered columns -> still parse correctly
        (format-forgiving, substring column detection)."""
        r = self._run(VN_REORDERED)
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_empty_report(self):
        r = self._run(EMPTY_REPORT)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_missing_file(self):
        r = run_gate("--report", "/nonexistent/x.REPORT.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("report not found", r.stderr)

    def test_fail_both_args_given(self):
        p = _write_tmp_report(FULL_REPORT)
        self.addCleanup(lambda: p.unlink(missing_ok=True))
        r = run_gate("--report", str(p), "--dir", str(p.parent))
        self.assertNotEqual(r.returncode, 0)

    def test_fail_neither_arg_given(self):
        r = run_gate()
        self.assertNotEqual(r.returncode, 0)

    def test_dir_resolves_latest_report(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [f.unlink() for f in d.glob("*")] and d.rmdir())
        (d / "REPORT.md").write_text(FULL_REPORT, encoding="utf-8")
        r = run_gate("--dir", str(d))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")

    def test_stdlib_only_import(self):
        """Grep-level confirmation that evidence.py imports nothing
        third-party (T-06-02 posture) — kept enforced in the test suite."""
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


class EvidenceGateParserUnitTests(unittest.TestCase):
    """Exercise evaluate_evidence() directly (no subprocess) — fast, precise,
    used for the perf/ReDoS guard and small parser edge cases."""

    def test_perf_large_input_is_linear_and_fast(self):
        header = "| TC-ID | Kịch bản | Kết quả | Method | Screenshot | Note |\n"
        sep = "|---|---|---|---|---|---|\n"
        rows = "".join(
            f"| TC-{i} | scenario {i} | ✅ PASS | UI click | ss-{i}.png | ok |\n"
            for i in range(5000)
        )
        text = header + sep + rows
        start = time.monotonic()
        ok, reason = evidence_gate.evaluate_evidence(text)
        elapsed = time.monotonic() - start
        self.assertTrue(ok, msg=reason)
        self.assertLess(elapsed, 1.0, msg=f"parse took {elapsed:.3f}s -- not linear?")

    def test_perf_pathological_input_is_fast_too(self):
        """Adversarial pipes/dashes that would blow up a catastrophic-backtracking
        regex; a linear parser must still finish comfortably under 1s (T-06-02)."""
        text = "| Kết quả | Method |\n" + (("|" * 200) + ("-" * 200) + "\n") * 500
        start = time.monotonic()
        evidence_gate.evaluate_evidence(text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)

    def test_whitespace_only_text_fails(self):
        ok, _reason = evidence_gate.evaluate_evidence("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _reason = evidence_gate.evaluate_evidence("")
        self.assertFalse(ok)

    def test_zero_subject_rows_no_tables_at_all_is_pass(self):
        ok, reason = evidence_gate.evaluate_evidence("# QA Report\n\nKhông có bảng nào.\n")
        self.assertTrue(ok, msg=reason)


if __name__ == "__main__":
    unittest.main()
