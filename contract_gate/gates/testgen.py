#!/usr/bin/env python3
"""Test-generation / RTM gate — mid-code hard block for the TEST-COVERAGE
layer (contract-gate gate #6, sibling of `golden_record.py` / `fidelity.py` /
`manifest.py` / `greenfield.py` / `data_binding.py`).

Where `greenfield`/`manifest` gate that a behavior has an Observable *before*
code is written, this gate gates that every behavior/requirement has at
least one **traced test case with a real oracle** before merge — a
Requirements Traceability Matrix (RTM). The methodology behind what a good
RTM row looks like (Equivalence Partitioning / Boundary Value Analysis /
decision tables / state-transition / pairwise, plus "mark `?` if the oracle
genuinely isn't clear, never invent a plausible expected result") comes from
the `senior-qa` test-design discipline — baked into DRAFT_GUIDANCE below as
portable prose, not a skill invocation, so this gate stays agent-agnostic.

RTM-01 (stdlib-only, hard verdict — mirrors golden_record.py's GOLD-01):
imports below are limited to argparse/sys/pathlib. NO third-party package,
NO subprocess, NO LLM call here — `check` never drafts a test case itself,
it only grades the structure of an RTM an agent/human already wrote (the
draft/check split, RTM-05). On success prints `pass <summary>` to stdout and
exits 0. On any failure prints `fail <one-line reason>` to stderr and exits
1.

RTM-02 (what counts as a qualifying table): a markdown pipe table whose
header row has BOTH a column recognizable as "Requirement"/"Behavior"/
"SHALL" (which behavior this test case traces to) AND a column recognizable
as "Expected"/"Oracle" (what a passing run must show). Test ID, Scenario/
Steps, Technique, Severity/Priority columns are optional and carried through
for the human but only Technique is graded (RTM-03.3).

RTM-03 (the gate — per row, in order):
  1. the Requirement/Behavior-ref cell must be non-empty/non-placeholder —
     a test case traced to nothing defeats the point of a traceability
     matrix (you cannot tell, from this row alone, which behavior it covers,
     so a requirement with zero real rows stays invisible as an uncovered
     gap instead of surfacing as one).
  2. the Expected/Oracle cell must be non-empty/non-placeholder — a `?` here
     is a HONEST, correct signal that the correct behavior for this case
     was never pinned down (from spec or design); it is meant to fail the
     gate and force a human to resolve it, not to silently pass through.
     Inventing a plausible-looking expected result to dodge this defeats
     the entire gate (this is the failure mode gate #6 exists to catch —
     "an AI guessed what should happen" is exactly as dangerous here as
     "an AI guessed the API response shape" is for `golden-record`).
  3. IF the table has an optional Technique column, each row's cell in it
     must be non-empty/non-placeholder too — tracking WHICH design
     technique (EP/BVA/decision-table/state-transition/pairwise/exploratory)
     produced a case is what stops an RTM from being N copies of the same
     happy-path shape (mirrors data_binding.py's optional format column and
     golden_record.py's optional Edge-case column — same "if you claim to
     track it, prove you tracked it" rule).
A cell that is whitespace-only, a lone dash look-alike, or a placeholder
word (?/TODO/TBD/WIP/…) counts as UNFILLED — identical rules to the other
four gates' `_is_empty_cell`, reused verbatim for consistency.

RTM-04 (multi-table files — scan the WHOLE file, ported preventively from
the identical D-07 bug already fixed once in `greenfield.py` and once in
`manifest.py`, and guarded against from the start in `fidelity.py`'s FID-05):
the row-scanning loop below never stops after the first qualifying table.

RTM-05 (draft symmetry — the opposite of golden_record.py's/fidelity.py's
GOLD-05/FID-07): unlike those two, an RTM row's Requirement-ref and even a
plausible Expected/Oracle CAN often be legitimately derived by an LLM
reading the spec/design directly — deriving what SHOULD happen from stated
behavior is exactly what EP/BVA/decision-table technique is FOR. So
DRAFT_GUIDANCE instructs the drafting agent to actually apply that
methodology and fill real rows, reserving `?` in Expected ONLY for cases
where the spec/design is itself genuinely silent or ambiguous about the
correct behavior — the opposite default from `golden-record`/`fidelity`,
where `?` is expected far more often than not.

RTM-06 (decision, deliberately NOT enforced here): this gate does NOT
cross-check RTM rows against the original spec/design to verify every SHALL/
behavior statement has >=1 covering row — that is a genuinely harder,
cross-file diff (closer in shape to `greenfield.py`'s Design-ref resolution,
but against a second document this gate doesn't take as input) and was
explicitly deferred as the hardest of the six gates. This gate only proves
that whatever rows ARE in the RTM are each traced and each carry a real (or
honestly-`?`) oracle — closing that remaining "did we even try to enumerate
every behavior" gap belongs to a future enhancement or to the human/agent's
own spec-reading discipline, not to a stdlib text-parsing gate re-deriving
completeness it has no second document to check against. This comment is
the record that RTM-06 was decided, not silently dropped.

Usage:
    python3 testgen.py --rtm <path/to/x.testgen.md>
    python3 testgen.py --repo <target-repo> --task <task>
        (resolves to <target-repo>/.port/<task>.testgen.md)
Exactly one of the two forms is required.

RTM-07 (deliberately narrow GLOBS, no generic `*.contract.md` catch-all —
mirrors manifest.py/greenfield.py/fidelity.py's FID-08, NOT data_binding.py/
golden_record.py): keeps this gate from self-discovering (and possibly
self-failing) `contract-gate init`'s `example.testgen.contract.md` scaffold.
Name a real RTM file `<task>.testgen.md`, not `.testgen.contract.md`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Identical UNFILLED rules to data_binding.py / golden_record.py / manifest.py
# / greenfield.py / fidelity.py — kept as a verbatim local copy rather than a
# cross-gate import so each gate module stays independently readable/
# reviewable (repo convention).
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−"}
PLACEHOLDER_WORDS = {"todo", "tbd", "wip", "?", "??", "...", "…", "xxx", "tba"}
_UNRESOLVED_PREFIXES = ("todo", "tbd", "wip", "tba")

# Header-detection needles (lowercase substrings, EN/VN).
REQ_NEEDLES = (
    "requirement", "behavior", "behaviour", "shall", "req id", "req-ref",
    "req ref", "yêu cầu", "yeu cau", "hành vi", "hanh vi",
)
EXPECTED_NEEDLES = (
    "expected", "oracle", "kỳ vọng", "ky vong", "kết quả mong đợi",
    "ket qua mong doi", "expected result",
)
TESTID_NEEDLES = ("test id", "test case", "tc id", "case id", "mã ca", "ma ca")
TECHNIQUE_NEEDLES = ("technique", "kỹ thuật", "ky thuat", "method")

# Optional delimiter — when present, only the enclosed block is scanned.
START = "<!-- testgen:start -->"
END = "<!-- testgen:end -->"


def _norm(cell: str) -> str:
    return cell.strip()


def _is_empty_cell(cell: str) -> bool:
    n = _norm(cell)
    if n in EMPTY_CELL_MARKERS:
        return True
    low = n.lower()
    if low in PLACEHOLDER_WORDS:
        return True
    if n.startswith("?"):
        return True
    for w in _UNRESOLVED_PREFIXES:
        if low == w or low.startswith(w + " ") or low.startswith(w + ":") or low.startswith(w + "-"):
            return True
    return False


def _looks_like_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    saw_dash = False
    for c in cells:
        c2 = c.strip()
        if not c2:
            continue
        if not set(c2) <= set("-: "):
            return False
        if "-" in c2:
            saw_dash = True
    return saw_dash


def _find_col(header_cells: list[str], needles: tuple[str, ...]) -> int | None:
    for i, cell in enumerate(header_cells):
        low = cell.lower()
        if any(needle in low for needle in needles):
            return i
    return None


def _extract_scope(text: str) -> str:
    i = text.find(START)
    if i < 0:
        return text
    j = text.find(END, i + len(START))
    if j < 0:
        return text[i + len(START):]
    return text[i + len(START):j]


def _row_label(cells: list[str], testid_col: int | None, req_col: int | None, idx: int) -> str:
    tid = _norm(cells[testid_col]) if testid_col is not None and testid_col < len(cells) else ""
    req = _norm(cells[req_col]) if req_col is not None and req_col < len(cells) else ""
    if tid and req:
        return f'"{tid}" (traces "{req}")'
    if tid:
        return f'"{tid}"'
    if req:
        return f'test case for "{req}" (row {idx})'
    return f"row {idx}"


def _skip_table_body(lines: list[str], start: int, n: int) -> int:
    k = start
    while k < n and _looks_like_table_row(lines[k]):
        k += 1
    return k


def _analyze(text: str) -> tuple[list[str], str]:
    """Single linear pass backing both evaluate() (fail-fast) and findings()
    (collect-all). Returns (findings, summary): non-empty findings = fail."""
    if not text or not text.strip():
        return ["RTM file empty"], ""

    lines = _extract_scope(text).splitlines()
    n = len(lines)

    fs: list[str] = []
    qualifying_tables = 0
    rows_total = 0

    i = 0
    while i < n:
        if not _looks_like_table_row(lines[i]):
            i += 1
            continue
        header_cells = _split_row(lines[i])
        if _is_separator_row(header_cells):
            i += 1
            continue

        req_col = _find_col(header_cells, REQ_NEEDLES)
        expected_col = _find_col(header_cells, EXPECTED_NEEDLES)
        if req_col is None or expected_col is None:
            i = _skip_table_body(lines, i + 1, n)
            continue

        qualifying_tables += 1
        testid_col = _find_col(header_cells, TESTID_NEEDLES)
        technique_col = _find_col(header_cells, TECHNIQUE_NEEDLES)

        j = i + 1
        if j < n and _looks_like_table_row(lines[j]) and _is_separator_row(_split_row(lines[j])):
            j += 1

        row_idx = 0
        while j < n and _looks_like_table_row(lines[j]):
            cells = _split_row(lines[j])
            if _is_separator_row(cells):
                j += 1
                continue
            row_idx += 1
            rows_total += 1
            label = _row_label(cells, testid_col, req_col, row_idx)

            req_cell = cells[req_col] if req_col < len(cells) else ""
            if _is_empty_cell(req_cell):
                fs.append(
                    f"{label} has no Requirement/Behavior reference — an untraced test case "
                    f"leaves that requirement's coverage invisible (RTM-03.1)"
                )
                j += 1
                continue

            expected_cell = cells[expected_col] if expected_col < len(cells) else ""
            if _is_empty_cell(expected_cell):
                fs.append(
                    f"{label} has no Expected/Oracle — mark `?` only when the spec/design "
                    f"genuinely doesn't pin the correct behavior, don't invent one (RTM-03.2), "
                    f"then resolve it before this gate can pass"
                )
                j += 1
                continue

            if technique_col is not None:
                technique_cell = cells[technique_col] if technique_col < len(cells) else ""
                if _is_empty_cell(technique_cell):
                    fs.append(f"{label} chưa khai Technique (EP/BVA/decision-table/state/pairwise/...)")
                    j += 1
                    continue

            j += 1

        i = j

    if qualifying_tables == 0:
        return [
            "no RTM table found (cần bảng có cột Requirement/Behavior + Expected/Oracle — RTM-02)"
        ], ""

    summary = f"{rows_total} test case(s) traced with a real oracle across {qualifying_tables} table(s)"
    return fs, summary


def evaluate_rtm(text: str) -> tuple[bool, str]:
    fs, summary = _analyze(text)
    if fs:
        return False, fs[0]
    return True, summary


def findings(text: str, path: Path | None = None) -> list[str]:
    """ALL failure reasons (empty = pass). `path` unused (no on-disk resolution)."""
    return _analyze(text)[0]


# --------------------------------------------------------------------------
# Gate descriptor — consumed by the contract-gate CLI registry.
# --------------------------------------------------------------------------

KEY = "testgen"
TITLE = "Test-generation RTM (traceability + oracle)"
# RTM-07: narrow on purpose — no "*.contract.md" catch-all (see module docstring).
GLOBS = ("*.testgen.md", "*RTM*.md", "*.rtm.md")


def contains_rtm_table(text: str) -> bool:
    """True iff `text` has at least one qualifying table (header with BOTH a
    Requirement/Behavior and an Expected/Oracle column) — lets the CLI skip
    files that merely share a generic name but hold a different contract."""
    for line in _extract_scope(text).splitlines():
        if not _looks_like_table_row(line):
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        if _find_col(cells, REQ_NEEDLES) is not None and _find_col(cells, EXPECTED_NEEDLES) is not None:
            return True
    return False


def applies(text: str) -> bool:
    return contains_rtm_table(text)


def evaluate(text: str, path: Path | None = None) -> tuple[bool, str]:
    # path unused — testgen needs no on-disk resolution.
    return evaluate_rtm(text)


DRAFT_GUIDANCE = """\
Draft a Requirements Traceability Matrix (RTM): for every behavior/
requirement in the source material, derive at least one real test case
using formal test-design technique — Equivalence Partitioning (valid/
invalid/boundary-adjacent classes), Boundary Value Analysis (3-value: just
below / at / just above each boundary), decision tables for combined
conditions, state-transition for wizards/multi-step flows, and pairwise for
large parameter combinations.

CRITICAL — how this gate differs from golden-record/fidelity:
- Requirement-ref and Expected/Oracle CAN and SHOULD usually be derived
  directly from the spec/design in --source — that is the whole point of
  applying EP/BVA/decision-table reasoning. Do not leave them `?` just
  because deriving them takes real thinking.
- Only write `?` in Expected when the source material is ITSELF silent or
  genuinely ambiguous about what the correct behavior is for that case —
  that `?` is the valuable signal (a real spec gap), not a shortcut.
- NEVER invent a plausible-sounding Expected result to fill a gap the spec
  doesn't actually resolve — that recreates exactly the "AI guessed what
  should happen" failure mode this gate exists to catch.
- Cover more than the happy path: for every field/behavior that can
  plausibly be null, zero, empty, at a boundary, or combined with another
  condition, add a case for it — one happy-path row per requirement defeats
  the purpose.
- If you add a Technique column, fill it for every row (EP/BVA/decision-
  table/state-transition/pairwise/exploratory) so someone can audit WHICH
  technique produced each case, not just that a case exists.

Output ONLY the completed markdown contract below (keep the table shape); no
prose before or after."""


TEMPLATE = """\
# Test-generation RTM — <feature/task>

> Mỗi requirement/behavior trong spec → ít nhất 1 ca test thật, có oracle
> thật (Expected). Suy Expected trực tiếp từ spec/design bằng EP/BVA/decision
> table — chỉ để `?` khi spec/design THẬT SỰ không nói rõ nên hành xử ra sao;
> đừng bịa Expected để lách gate. Phủ cả biên/null/kết hợp điều kiện, không
> chỉ happy-path.

<!-- testgen:start -->
| Requirement | Test ID | Technique | Test data / Steps | Expected / Oracle |
|-------------|---------|-----------|--------------------|--------------------|
| <req/behavior id> | TC-01 | EP (valid) | <input hợp lệ điển hình> | <kết quả đúng nên xảy ra> |
| <req/behavior id> | TC-02 | BVA (boundary) | <input đúng ngay ranh giới> | <kết quả đúng nên xảy ra> |
<!-- testgen:end -->
"""


def resolve_rtm_path(args: argparse.Namespace) -> Path:
    if args.rtm:
        return Path(args.rtm)
    return Path(args.repo) / ".port" / f"{args.task}.testgen.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="testgen_gate",
        description=(
            "Mid-code hard block (RTM-01): verify every RTM row traces to a "
            "Requirement/Behavior and carries a real (or honestly-`?`) "
            "Expected/Oracle."
        ),
    )
    p.add_argument("--rtm", help="Path to the RTM markdown file")
    p.add_argument("--repo", help="Target repo root (used together with --task)")
    p.add_argument("--task", help="Task slug (used together with --repo)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    has_rtm = bool(args.rtm)
    has_repo_task = bool(args.repo) and bool(args.task)
    has_partial_repo_task = bool(args.repo) != bool(args.task)

    if has_rtm and (args.repo or args.task):
        print("fail specify --rtm OR --repo+--task, not both", file=sys.stderr)
        return 1
    if has_partial_repo_task:
        print("fail --repo and --task must be given together", file=sys.stderr)
        return 1
    if not has_rtm and not has_repo_task:
        print("fail either --rtm or both --repo and --task are required", file=sys.stderr)
        return 1

    path = resolve_rtm_path(args)
    if not path.exists() or path.is_dir():
        print("fail RTM file not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read RTM file: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate_rtm(text)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
