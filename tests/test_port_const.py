#!/usr/bin/env python3
"""Stdlib unittest for contract_gate/gates/port_const.py (PCONST-01, gate #7).

Mirrors test_data_binding.py / test_golden_record.py 1:1 (subprocess CLI
harness, case matrix, stdlib-import test) plus the port-const-specific
cases: locator-cell parsing, file resolution relative to the contract
file's own directory, the literal-extraction core (list/scalar/enum-object,
quote-aware bracket balancing), the symmetric-diff verdict (missing vs
extra reported separately), and the header-qualification guard (source+built
required, label/kind optional, GOLD-06-style collision discipline).

Run: cd <repo root> && python3 -m unittest tests/test_port_const.py -v
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
GATE = REPO_ROOT / "contract_gate" / "gates" / "port_const.py"
FIXTURES = TESTS_DIR / "fixtures" / "port_const"

sys.path.insert(0, str(REPO_ROOT))
from contract_gate.gates import port_const as port_const_gate  # noqa: E402


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class PortConstGateCLITests(unittest.TestCase):
    """CLI-level cases -- exercise the real `python3 port_const.py ...`,
    resolving locator files relative to the contract file's own directory."""

    def test_pass_matching_list(self):
        """Case 1: source + built declare the SAME prefecture list -> pass."""
        r = run_gate("--map", str(FIXTURES / "pass.portconst.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)
        self.assertIn("1 port-constant(s) verified", r.stdout)

    def test_fail_built_missing_entries_names_the_missing_value(self):
        """Case 2: built silently dropped 北海道-06..10 during port -> fail,
        and the finding NAMES a missing value (the real bug class this gate
        exists to catch)."""
        r = run_gate("--map", str(FIXTURES / "fail-missing.portconst.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("MISSING", r.stderr)
        self.assertIn("北海道-06", r.stderr)

    def test_fail_built_extra_entry_names_the_extra_value(self):
        """Case 3: built has an entry not present in the legacy source ->
        fail, and the finding NAMES the extra value."""
        r = run_gate("--map", str(FIXTURES / "fail-extra.portconst.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("EXTRA", r.stderr)
        self.assertIn("沖縄県-EXTRA", r.stderr)

    def test_pass_scalar_match(self):
        """Case 4 (match half): kind=scalar, source and built agree -> pass."""
        r = run_gate("--map", str(FIXTURES / "pass-scalar.portconst.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_scalar_mismatch(self):
        """Case 4 (mismatch half): kind=scalar, comparator direction
        reversed during port -> fail."""
        r = run_gate("--map", str(FIXTURES / "fail-scalar-mismatch.portconst.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("chibanSortOrder-asc", r.stderr)
        self.assertIn("chibanSortOrder-desc", r.stderr)

    def test_fail_locator_not_found_in_built(self):
        """Case 5: the identifier was renamed during port and no longer
        exists in the built file -> fail with 'not found'."""
        r = run_gate("--map", str(FIXTURES / "fail-locator-not-found.portconst.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("not found", r.stderr)
        self.assertIn("PREFECTURE_OPTIONS", r.stderr)

    def test_fail_unreadable_built_file_is_not_a_silent_pass(self):
        """Case 6: the declared built file does not exist -> fail loudly,
        never a silent pass (advisory tier, loud-over-silent)."""
        r = run_gate("--map", str(FIXTURES / "fail-unreadable-file.portconst.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("not found", r.stderr)
        self.assertIn("does_not_exist.ts", r.stderr)

    def test_pass_quote_bracket_extraction_robustness(self):
        """Case 8: a string element containing a raw ']' character must NOT
        prematurely close the array (string-skipping in the balanced-bracket
        scan) -> both sides extract the same 2-element set -> pass."""
        r = run_gate("--map", str(FIXTURES / "pass-quote-bracket.portconst.md"))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_fail_no_table(self):
        """No table with both a Source and a DISTINCT Built column -> fail."""
        r = run_gate("--map", str(FIXTURES / "fail-no-table.portconst.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)
        self.assertIn("no port-constant table found", r.stderr)

    def test_fail_empty_file(self):
        """File exists but is whitespace-only -> fail."""
        r = run_gate("--map", str(FIXTURES / "fail-empty-file.portconst.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_missing_file(self):
        """Path does not exist -> exit!=0, reason names the missing file."""
        r = run_gate("--map", "/nonexistent/x.portconst.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("port-const file not found", r.stderr)

    def test_fail_both_forms(self):
        """--map together with --repo/--task is rejected."""
        r = run_gate("--map", "x.md", "--repo", "r", "--task", "t")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_fail_partial_repo_task(self):
        """--repo without --task (or vice versa) is rejected."""
        r = run_gate("--repo", "r")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail", r.stderr)

    def test_path_resolved_relative_to_contract_file_not_cwd(self):
        """Invoking with an ABSOLUTE --map path from an unrelated cwd still
        resolves the relative source/built locator cells against the
        contract file's OWN directory (PCONST-05), not the process cwd."""
        r = subprocess.run(
            [sys.executable, str(GATE), "--map", str(FIXTURES / "pass.portconst.md")],
            capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
        )
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pass", r.stdout)

    def test_stdlib_only_import(self):
        """Grep-level confirmation that port_const.py imports nothing
        third-party (PCONST-01) — no AST/JS-parser library either."""
        src = GATE.read_text(encoding="utf-8")
        stdlib_ok_prefixes = (
            "import argparse", "import sys", "from pathlib", "from __future__",
            "from .. import tableparse", "from contract_gate import tableparse",
        )
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


class PortConstExtractionUnitTests(unittest.TestCase):
    """Exercise extract_literal_set() directly -- the novel core, fast and
    precise, including the quote-inside-bracket robustness case."""

    def test_list_extraction_matches(self):
        text = "export const X = ['a', 'b', 'c'];\n"
        self.assertEqual(
            port_const_gate.extract_literal_set(text, "X", "list"), {"a", "b", "c"}
        )

    def test_scalar_extraction(self):
        text = "export const X = 'value';\n"
        self.assertEqual(port_const_gate.extract_literal_set(text, "X", "scalar"), {"value"})

    def test_enum_object_extraction_uses_keys(self):
        """Object-literal enums extract KEYS, not values (documented design
        choice, PCONST-04)."""
        text = "export const X = {\n  HOKKAIDO: 'north',\n  TOKYO: 'east',\n};\n"
        self.assertEqual(
            port_const_gate.extract_literal_set(text, "X", "list"), {"HOKKAIDO", "TOKYO"}
        )

    def test_bracket_char_inside_quoted_string_does_not_close_early(self):
        """Case 8 at the unit level: a `]` embedded in a quoted array
        element must not be mistaken for the array's real closing bracket."""
        text = "export const X = [\n  'a [not a close]',\n  'b',\n];\n"
        result = port_const_gate.extract_literal_set(text, "X", "list")
        self.assertEqual(result, {"a [not a close]", "b"})

    def test_locator_not_found_returns_none(self):
        text = "export const Y = ['a'];\n"
        self.assertIsNone(port_const_gate.extract_literal_set(text, "X", "list"))

    def test_identifier_boundary_not_a_substring_match(self):
        """`X` must not match inside `X_OTHER` — boundary-checked search."""
        text = "export const X_OTHER = ['z'];\n"
        self.assertIsNone(port_const_gate.extract_literal_set(text, "X", "list"))

    def test_comparison_operator_is_not_mistaken_for_assignment(self):
        """`X === something` (a comparison) must not be read as `X`'s
        declaration; the REAL declaration further down must still be found."""
        text = "if (kind === X) { doThing(); }\nexport const X = ['ok'];\n"
        self.assertEqual(port_const_gate.extract_literal_set(text, "X", "list"), {"ok"})

    def test_object_key_colon_style_declaration(self):
        """An object-literal-key style declaration (`X: [...]`) is found,
        not just `export const X = [...]`."""
        text = "const CONFIG = {\n  X: ['a', 'b'],\n};\n"
        self.assertEqual(port_const_gate.extract_literal_set(text, "X", "list"), {"a", "b"})


class PortConstHeaderQualificationUnitTests(unittest.TestCase):
    """applies()/header-resolution — the GOLD-06-style collision guard."""

    def test_applies_true_for_qualifying_table(self):
        text = (
            "| Constant | Source (legacy) | Built (react) | Kind |\n"
            "|--|--|--|--|\n"
            "| x | a.js#X | b.ts#X | list |\n"
        )
        self.assertTrue(port_const_gate.applies(text))

    def test_applies_false_when_no_distinct_built_column(self):
        """Case 7: a table with only a Source column (no Built column at
        all) must NOT be claimed by this gate -- proves it doesn't hijack
        other contracts (e.g. a data-binding-shaped table)."""
        text = (
            "| Constant | Source (legacy) |\n"
            "|--|--|\n"
            "| x | a.js#X |\n"
        )
        self.assertFalse(port_const_gate.applies(text))

    def test_applies_false_for_golden_record_table(self):
        """A differently-shaped contract (Expected/Actual, no Source/Built)
        must not be claimed -- a gate never judges a file it does not own."""
        text = "| Record | Expected | Actual |\n|--|--|--|\n| a | 1 | 1 |\n"
        self.assertFalse(port_const_gate.applies(text))

    def test_label_and_kind_columns_are_optional(self):
        """No Constant/label column and no Kind column at all -- still
        qualifies and grades (defaults to kind=list, generic row label)."""
        text = (
            "| Source (legacy) | Built (react) |\n"
            "|--|--|\n"
            "| a.js#X | b.ts#X |\n"
        )
        self.assertTrue(port_const_gate.applies(text))

    def test_reordered_columns_still_qualify(self):
        """Column order is free -- Built before Source, Kind before both."""
        text = (
            "| Kind | Built (react) | Constant | Source (legacy) |\n"
            "|--|--|--|--|\n"
            "| list | b.ts#X | x | a.js#X |\n"
        )
        self.assertTrue(port_const_gate.applies(text))


class PortConstAnalyzeUnitTests(unittest.TestCase):
    """Exercise evaluate_map()/findings() directly against on-disk fixture
    files, using an explicit `path` so relative locator cells resolve."""

    def _map_path(self, name: str) -> Path:
        return FIXTURES / name

    def test_evaluate_map_pass(self):
        p = self._map_path("pass.portconst.md")
        ok, reason = port_const_gate.evaluate_map(p.read_text(encoding="utf-8"), p)
        self.assertTrue(ok, msg=reason)

    def test_evaluate_map_fail_missing_names_value(self):
        p = self._map_path("fail-missing.portconst.md")
        ok, reason = port_const_gate.evaluate_map(p.read_text(encoding="utf-8"), p)
        self.assertFalse(ok)
        self.assertIn("北海道-06", reason)

    def test_malformed_locator_cell_fails_loudly(self):
        """A locator cell with no `#` separator is MALFORMED -- fails
        rather than silently passing or crashing."""
        text = (
            "| Constant | Source (legacy) | Built (react) |\n"
            "|--|--|--|\n"
            "| x | no-hash-here | b.js#X |\n"
        )
        ok, reason = port_const_gate.evaluate_map(text, None)
        self.assertFalse(ok)
        self.assertIn("malformed source locator", reason)

    def test_placeholder_source_cell_fails_loudly(self):
        """A bare `?` placeholder locator cell has no `#` -- MALFORMED,
        never a silent pass."""
        text = (
            "| Constant | Source (legacy) | Built (react) |\n"
            "|--|--|--|\n"
            "| x | ? | b.js#X |\n"
        )
        ok, reason = port_const_gate.evaluate_map(text, None)
        self.assertFalse(ok)
        self.assertIn("malformed source locator", reason)

    def test_header_only_table_fails(self):
        """A bare header with zero body rows is an ungraded claim -- fail,
        mirroring DBIND-02/GOLD-02's F7 fix."""
        text = "| Constant | Source | Built |\n|--|--|--|\n"
        ok, reason = port_const_gate.evaluate_map(text, None)
        self.assertFalse(ok)
        self.assertIn("no rows", reason)

    def test_findings_lists_every_problem_row(self):
        text = (
            "| Constant | Source | Built |\n"
            "|--|--|--|\n"
            "| a | bad-cell-1 | b.js#X |\n"
            "| b | s.js#Y | bad-cell-2 |\n"
        )
        fs = port_const_gate.findings(text, None)
        self.assertEqual(len(fs), 2)

    def test_whitespace_only_text_fails(self):
        ok, _ = port_const_gate.evaluate_map("   \n\n\t \n")
        self.assertFalse(ok)

    def test_empty_string_fails(self):
        ok, _ = port_const_gate.evaluate_map("")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
