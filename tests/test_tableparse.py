#!/usr/bin/env python3
"""Stdlib unittest for contract_gate/tableparse.py — the shared table-parsing
module every gate imports. These tests pin the family-wide semantics; the
per-gate test files pin each gate's use of them.

Run: cd <repo root> && python3 -m unittest tests/test_tableparse.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from contract_gate import tableparse as tp  # noqa: E402


class IsEmptyCellTests(unittest.TestCase):
    def test_dash_lookalikes_and_blank(self):
        for cell in ("", "   ", "-", "—", "–", "ー", "−"):
            self.assertTrue(tp.is_empty_cell(cell), msg=repr(cell))

    def test_placeholder_words(self):
        for cell in ("TODO", "tbd", "WIP", "?", "??", "...", "xxx", "TBA"):
            self.assertTrue(tp.is_empty_cell(cell), msg=repr(cell))

    def test_leading_question_mark_with_reason(self):
        self.assertTrue(tp.is_empty_cell("? endpoint not in spec"))

    def test_todo_prefix_with_annotation(self):
        for cell in ("TODO: ask BE", "tbd - waiting on design", "WIP still checking"):
            self.assertTrue(tp.is_empty_cell(cell), msg=repr(cell))

    def test_midstring_question_mark_is_filled(self):
        self.assertFalse(tp.is_empty_cell("GET /x?id=1"))

    def test_na_is_filled(self):
        self.assertFalse(tp.is_empty_cell("N/A — always set by API"))

    def test_whole_cell_angle_bracket_scaffold_is_empty(self):
        for cell in ("<screen-id>", "<giá trị thật từ DB>", "<path/to/report.json>"):
            self.assertTrue(tp.is_empty_cell(cell), msg=repr(cell))

    def test_partial_angle_bracket_is_filled(self):
        # A cell merely mentioning tags/comparisons is NOT a scaffold placeholder.
        for cell in ("<input> shows <value>", "load < 0.5s", "pin <marker> appears"):
            self.assertFalse(tp.is_empty_cell(cell), msg=repr(cell))


class SplitRowTests(unittest.TestCase):
    def test_plain_row(self):
        self.assertEqual(tp.split_row("| a | b | c |"), ["a", "b", "c"])

    def test_no_leading_or_trailing_pipe(self):
        self.assertEqual(tp.split_row("a | b | c"), ["a", "b", "c"])

    def test_empty_last_cell_kept_with_trailing_pipe(self):
        self.assertEqual(tp.split_row("| a |  |"), ["a", ""])

    def test_escaped_pipe_stays_in_cell(self):
        self.assertEqual(tp.split_row(r"| a | b \| c | d |"), ["a", "b | c", "d"])

    def test_pipe_inside_code_span_stays_in_cell(self):
        self.assertEqual(
            tp.split_row("| a | `GET /x?a=1|2` | d |"), ["a", "`GET /x?a=1|2`", "d"]
        )

    def test_unbalanced_backtick_falls_back_to_plain_split(self):
        # One lone backtick must not swallow the rest of the row into one cell.
        self.assertEqual(tp.split_row("| don`t | b | c |"), ["don`t", "b", "c"])

    def test_escaped_pipe_at_cell_end(self):
        self.assertEqual(tp.split_row(r"| a | b\| |"), ["a", "b|"])


class FindColTests(unittest.TestCase):
    def test_first_match(self):
        self.assertEqual(tp.find_col(["A", "Type", "Source"], ("type",)), 1)

    def test_exclude_skips_claimed_column(self):
        header = ["Expected behavior", "Steps"]
        self.assertEqual(tp.find_col(header, ("expected",)), 0)
        self.assertIsNone(tp.find_col(header, ("behavior",), exclude=frozenset({0})))

    def test_no_match(self):
        self.assertIsNone(tp.find_col(["A", "B"], ("zzz",)))


class ExtractScopeTests(unittest.TestCase):
    S, E = "<!-- x:start -->", "<!-- x:end -->"

    def test_no_marker_returns_whole_text(self):
        self.assertEqual(tp.extract_scope("abc", self.S, self.E), "abc")

    def test_single_block(self):
        text = f"before\n{self.S}\ninside\n{self.E}\nafter"
        self.assertEqual(tp.extract_scope(text, self.S, self.E).strip(), "inside")

    def test_all_blocks_scanned_not_just_first(self):
        text = f"{self.S}\nblock1\n{self.E}\nprose\n{self.S}\nblock2\n{self.E}\n"
        scope = tp.extract_scope(text, self.S, self.E)
        self.assertIn("block1", scope)
        self.assertIn("block2", scope)
        self.assertNotIn("prose", scope)

    def test_unterminated_final_block_runs_to_eof(self):
        text = f"{self.S}\nblock1\n{self.E}\n{self.S}\ntail"
        scope = tp.extract_scope(text, self.S, self.E)
        self.assertIn("block1", scope)
        self.assertIn("tail", scope)


def _resolve_obs(cells):
    col = tp.find_col(cells, ("observable",))
    return {"obs_col": col} if col is not None else None


class IterTablesTests(unittest.TestCase):
    def test_single_table(self):
        lines = [
            "| # | Behavior | Observable |",
            "|--|--|--|",
            "| 1 | x | dom check |",
        ]
        tables = tp.iter_tables(lines, _resolve_obs)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["obs_col"], 2)
        self.assertEqual((tables[0]["row_start"], tables[0]["row_end"]), (2, 3))

    def test_abutting_qualifying_tables_split_correctly(self):
        lines = [
            "| # | Behavior | Observable |",
            "|--|--|--|",
            "| 1 | x | dom check |",
            "| # | Observable | Behavior |",   # abuts — no blank line
            "|--|--|--|",
            "| 2 | - | click y |",
        ]
        tables = tp.iter_tables(lines, _resolve_obs)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["row_end"], 3)  # does NOT swallow table 2
        self.assertEqual(tables[1]["obs_col"], 1)  # table 2 keeps its OWN layout

    def test_non_qualifying_table_does_not_swallow_abutting_qualifying_table(self):
        lines = [
            "| Note | Comment |",
            "|--|--|",
            "| a | b |",
            "| # | Behavior | Observable |",   # abuts the note table
            "|--|--|--|",
            "| 1 | x |  |",
        ]
        tables = tp.iter_tables(lines, _resolve_obs)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["header_idx"], 3)

    def test_body_row_containing_needle_is_not_a_header(self):
        lines = [
            "| # | Behavior | Observable |",
            "|--|--|--|",
            "| 1 | shows observable hint | dom check |",  # needle word in body
            "| 2 | y | net call |",
        ]
        tables = tp.iter_tables(lines, _resolve_obs)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["row_end"], 4)

    def test_header_only_table_yields_zero_rows(self):
        lines = ["| # | Behavior | Observable |", "|--|--|--|"]
        tables = tp.iter_tables(lines, _resolve_obs)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["row_start"], tables[0]["row_end"])


if __name__ == "__main__":
    unittest.main()
