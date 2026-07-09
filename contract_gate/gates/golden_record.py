#!/usr/bin/env python3
"""Golden-record gate — pre-BUILD/early-verify hard block for the data-CORRECTNESS
layer (TOOL-REQUIREMENTS R5, contract-gate gate #4).

Fourth sibling of `data_binding.py` / `greenfield.py` / `manifest.py`: same
stdlib-only + `pass`/`fail` prefix + exit 0/1 contract. Where `data-binding`
gates that a source is DECLARED (R4 — "ô data chưa ghi nguồn = chưa cho
build"), this gate closes the layer R4 cannot reach: a declared source is
still a HYPOTHESIS (DP4) — `sale.price` might be wired to the wrong column
and still "have a source". The only way to know the wiring is actually
correct is to pick ONE record whose real answer is already known (queried
straight from the DB/API, not inferred from a spec) and check that the UI
the app actually renders for that record matches it.

Why this layer specifically (market context, not imagination): a 2026-07-06
market scan (95-agent deep-research) found mature tooling for visual/design
fidelity (Applitools, OverlayQA) and an emerging entrant for interaction/
logic wiring (Shiplight AI), but NO tool anywhere addressing "an AI coding
agent guessed the API/DB response shape wrong". This gate is the one piece
of contract-gate that targets that specific, otherwise-unserved failure
mode — see the 3 recurring bug classes it exists to catch (thiếu chữ /
thiếu logic / sai data): this is the "sai data" layer.

GOLD-01 (stdlib-only, hard verdict — mirrors data_binding.py's DBIND-01):
imports below are limited to argparse/sys/pathlib. NO third-party package,
NO network, NO DB driver — this gate NEVER queries a database or drives a
browser itself (that would break the zero-dep/agent-agnostic contract and
also just relocate the "trust me" problem). It only gates a markdown
artifact where a human/agent has ALREADY pinned the real answer and the
real on-screen result side by side. On success prints `pass <summary>` to
stdout and exits 0; on failure prints `fail <one-line reason>` to stderr
and exits 1.

GOLD-02 (what counts as a golden-record table): a markdown pipe table whose
header row has BOTH a column recognizable as **Expected** (the real DB/API
truth) AND a column recognizable as **Actual** (what the running app really
displayed). Record/Field columns are optional but used for the failure
label when present. Column order/count is free (reorder-tolerant), multiple
qualifying tables in one file are all evaluated. An optional
`<!-- golden-record:start --> ... <!-- golden-record:end -->` delimiter
restricts the scan to that block, mirroring data_binding.py's DBIND-02.

GOLD-03 (the gate — per row, in order):
  1. Expected must be non-empty/non-placeholder — an unpinned Expected means
     the "golden" record was never actually queried from reality; the
     contract is still just a hypothesis (DP4).
  2. Actual must be non-empty/non-placeholder — an unfilled Actual means
     nobody has yet looked at the real running app for this record; the
     comparison this gate exists to force has simply not happened yet.
  3. If BOTH are filled, they must match EXACTLY after stripping whitespace.
     Deliberately NOT normalized (no currency/format stripping): a format
     drift (`1,000,000` vs `¥1,000,000`) is itself a real bug class this
     project has hit before, not noise to smooth over. This means Expected
     must be written as the CORRECTLY RENDERED string the UI should show
     (e.g. `¥29,880,000`, or `—` for a null price) — NOT the bare raw DB
     value (`29880000`, or the literal word `null`) — because Expected and
     Actual are compared as display strings, not as underlying data.
  4. IF the table has an Edge-case column (optional, like data_binding's
     format column), each row's cell in it must be non-empty/non-placeholder
     — tracking WHICH boundary condition (null / 0 / very-long-number /
     locale-format) a row is pinned against is what stops every golden
     record in a file from silently being the same happy-path value.
A cell that is whitespace-only, a lone dash look-alike, or a placeholder
word (?/TODO/TBD/WIP/…) counts as UNFILLED — identical rules to
data_binding.py's `_is_empty_cell` (including the leading-`?`-with-reason
case), reused verbatim for consistency across the gate family.

GOLD-04 (DoS posture, inherited from siblings): linear line-by-line scan
using only str.split("|") — no regex, no catastrophic-backtracking surface.

GOLD-05 (draft asymmetry — the one thing that makes this gate different than
its siblings): `data-binding`/`greenfield`/`manifest` drafts can reasonably
be inferred by an LLM reading a spec/design, because the spec IS the oracle
for those layers. Expected/Actual here are NOT inferrable that way — Expected
must come from actually querying the real DB/API, and Actual must come from
actually looking at the real running app. An LLM asked to fill either
column just by reading spec text alone would recreate the exact "AI guessed
the data" bug this gate exists to catch. DRAFT_GUIDANCE below is written to
make that failure mode explicit and instructs marking both columns `?`
unless real queried/observed data is available in --source.

GOLD-06 (header-needle collision guard — real bug, found 2026-07-09 while
adding `fidelity.py`/`testgen.py`): `_find_col` originally matched a needle
list against a header cell with no memory of columns already claimed by an
earlier field. TEMPLATE's own header —
`Expected (DB thật, viết đúng dạng hiển thị)` — contains the VN substring
"hiển thị", which is also an ACTUAL_NEEDLES entry (VN for "displayed"); a
bare left-to-right `_find_col(header, ACTUAL_NEEDLES)` therefore resolved
`actual_col` to the *Expected* column instead of the real `Actual (UI thật)`
column next to it, silently comparing Expected against itself. This is why
`evaluate_map(TEMPLATE)` reported `pass` even though TEMPLATE's real Expected
and Actual cells hold deliberately DIFFERENT placeholder text — a false PASS
nobody had actually verified. Fixed: `_find_col` now takes an `exclude` set
of column indices already claimed by another field, and columns are
resolved in priority order — expected_col, then actual_col (excluding
expected_col), then record_col/field_col/edge_col (excluding both) — so no
two fields can ever silently resolve to the same column.

GOLD-07 (GLOBS narrowed, no bare-substring catch-all — mirrors manifest.py/
greenfield.py, and the same fix later applied to fidelity.py's FID-08/
testgen.py's RTM-07): `*golden-record*.md`/`*GOLDEN-RECORD*.md` matched
`contract-gate init`'s own scaffold filename
(`example.golden-record.contract.md`) as a bare substring. Once GOLD-06
made comparison correct, that self-match would have made the scaffold
self-FAIL (TEMPLATE's Expected != Actual, for real this time) instead of
the accidental self-pass it had before. Removed those two broad globs,
keeping only the suffix-anchored `*.goldenrecord.md` / `*.golden-record.md`
— neither matches `...contract.md`, so a real golden-record file must be
named `<screen>.goldenrecord.md` or `<screen>.golden-record.md`, not
`<screen>.golden-record.contract.md`.

Usage:
    python3 golden_record.py --map <path/to/golden-record.md>
    python3 golden_record.py --repo <target-repo> --task <task>
        (resolves to <target-repo>/.port/<task>.goldenrecord.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Optional delimiter — when present, only the enclosed block is scanned.
START = "<!-- golden-record:start -->"
END = "<!-- golden-record:end -->"

# Identical UNFILLED rules to data_binding.py (GOLD-03 note) — kept as a
# verbatim local copy rather than a cross-gate import so each gate module
# stays independently readable/reviewable (repo convention).
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−"}
PLACEHOLDER_WORDS = {"todo", "tbd", "wip", "?", "??", "...", "…", "xxx", "tba"}
_UNRESOLVED_PREFIXES = ("todo", "tbd", "wip", "tba")

# Header-detection needles (lowercase substrings, EN/VN).
RECORD_NEEDLES = ("record", "bản ghi", "ban ghi", "property id", "record id")
FIELD_NEEDLES = ("field", "element", "phần tử", "phan tu", "attribute", "cột", "cot")
EXPECTED_NEEDLES = (
    "expected", "kỳ vọng", "ky vong", "golden", "ground truth",
    "đáp án", "dap an", "db thật", "db that", "real value",
)
ACTUAL_NEEDLES = (
    "actual", "thực tế", "thuc te", "hiển thị", "hien thi",
    "displayed", "captured", "on-screen", "on screen", "rendered",
)
EDGECASE_NEEDLES = ("edge", "biên", "bien", "boundary", "edge case", "edge-case")


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


def _find_col(
    header_cells: list[str], needles: tuple[str, ...], exclude: frozenset[int] = frozenset()
) -> int | None:
    """First column matching any needle, skipping indices already claimed by
    another field (GOLD-06) — prevents two fields silently resolving to the
    same column when their needle lists share a substring."""
    for i, cell in enumerate(header_cells):
        if i in exclude:
            continue
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


def _row_label(cells: list[str], record_col: int | None, field_col: int | None, idx: int) -> str:
    record = _norm(cells[record_col]) if record_col is not None and record_col < len(cells) else ""
    field = _norm(cells[field_col]) if field_col is not None and field_col < len(cells) else ""
    if record and field:
        return f'"{record} × {field}"'
    if field:
        return f'"{field}"'
    if record:
        return f'"{record}" (row {idx})'
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
        return ["golden-record file empty"], ""

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

        # GOLD-06: resolve in priority order, each excluding columns already
        # claimed — expected/actual are the load-bearing pair (compared for
        # equality) so they're resolved first and mutually exclusive.
        expected_col = _find_col(header_cells, EXPECTED_NEEDLES)
        actual_col = _find_col(
            header_cells, ACTUAL_NEEDLES,
            exclude=frozenset({expected_col}) if expected_col is not None else frozenset(),
        )
        if expected_col is None or actual_col is None:
            i = _skip_table_body(lines, i + 1, n)
            continue

        qualifying_tables += 1
        claimed = frozenset({expected_col, actual_col})
        record_col = _find_col(header_cells, RECORD_NEEDLES, exclude=claimed)
        claimed = claimed | (frozenset({record_col}) if record_col is not None else frozenset())
        field_col = _find_col(header_cells, FIELD_NEEDLES, exclude=claimed)
        claimed = claimed | (frozenset({field_col}) if field_col is not None else frozenset())
        edge_col = _find_col(header_cells, EDGECASE_NEEDLES, exclude=claimed)

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
            label = _row_label(cells, record_col, field_col, row_idx)

            expected_cell = cells[expected_col] if expected_col < len(cells) else ""
            if _is_empty_cell(expected_cell):
                fs.append(
                    f"golden record {label} has no Expected value — chưa pin đáp án thật "
                    f"từ DB/API (R5: contract là hypothesis cho tới khi verify vs reality)"
                )
                j += 1
                continue

            actual_cell = cells[actual_col] if actual_col < len(cells) else ""
            if _is_empty_cell(actual_cell):
                fs.append(
                    f"golden record {label} has no Actual value — chưa capture UI thật "
                    f"đang hiển thị gì cho record này"
                )
                j += 1
                continue

            if _norm(expected_cell) != _norm(actual_cell):
                fs.append(
                    f'golden record {label}: expected "{_norm(expected_cell)}" '
                    f'but actual "{_norm(actual_cell)}" — data sai/lệch với DB thật'
                )
                j += 1
                continue

            if edge_col is not None:
                edge_cell = cells[edge_col] if edge_col < len(cells) else ""
                if _is_empty_cell(edge_cell):
                    fs.append(
                        f"golden record {label} chưa khai edge-case đang test "
                        f"(null/0/số dài/format...)"
                    )
                    j += 1
                    continue

            j += 1

        i = j

    if qualifying_tables == 0:
        return [
            "no golden-record table found "
            "(cần bảng có cột Expected + Actual — R5 2-column oracle)"
        ], ""

    summary = f"{rows_total} golden record(s) verified against real DB/UI truth across {qualifying_tables} table(s)"
    return fs, summary


def evaluate_map(text: str) -> tuple[bool, str]:
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

KEY = "golden-record"
TITLE = "Golden-record data verification"
# GOLD-07: narrow on purpose — no bare-substring/"*.contract.md" catch-all.
GLOBS = ("*.goldenrecord.md", "*.golden-record.md")


def contains_golden_record_table(text: str) -> bool:
    """True iff `text` has at least one qualifying table (header with BOTH an
    Expected and a DISTINCT Actual column) — lets the CLI skip files that
    merely share a generic name but hold a different kind of contract."""
    for line in _extract_scope(text).splitlines():
        if not _looks_like_table_row(line):
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        expected_col = _find_col(cells, EXPECTED_NEEDLES)
        if expected_col is None:
            continue
        actual_col = _find_col(cells, ACTUAL_NEEDLES, exclude=frozenset({expected_col}))
        if actual_col is not None:
            return True
    return False


def applies(text: str) -> bool:
    return contains_golden_record_table(text)


def evaluate(text: str, path: Path | None = None) -> tuple[bool, str]:
    # path unused — golden-record needs no on-disk resolution.
    return evaluate_map(text)


DRAFT_GUIDANCE = """\
Draft a Golden-record verification table: pick 1 real record and pin its
REAL answer next to what the running app REALLY displays for it.

CRITICAL — this gate is fundamentally different from a spec-derived contract:
- Expected MUST come from actually querying the real DB/API for this exact
  record — NEVER infer or guess it from a spec/design description. If the
  --source material given to you does not contain real queried data (e.g. an
  actual DB row dump or API response, not just prose), leave Expected as `?`.
- Write Expected as the CORRECTLY RENDERED display string (e.g. `¥29,880,000`,
  or `—` for a null price) — NOT the bare raw DB value (`29880000`, or the
  literal word `null`). Expected and Actual are compared as display strings.
- Actual MUST come from actually opening the real running app and reading
  what it shows for this exact record — you (the drafting agent) cannot see
  a live screen from static source text. ALWAYS leave every Actual cell as
  `?` unless the source material explicitly includes a captured screenshot
  transcript or DOM dump of the real app state.
- Cover at least one boundary case if the field can plausibly be null, zero,
  a very long number, or specially formatted (currency, JP 万円, etc.) — one
  happy-path record alone defeats the purpose (R5).

NEVER invent a plausible-looking value for either column to make the gate
pass — a `?` is correct and expected here far more often than in other
gates; it marks exactly the human/agent step (query the DB, open the app)
that still has to happen before this contract means anything.

Output ONLY the completed markdown contract below (keep the table shape); no
prose before or after."""


TEMPLATE = """\
# Golden-record verification — <screen/feature>

> Pin ĐÚNG 1 record thật (biết trước đáp án) rồi so khớp UI thật hiển thị gì.
> Expected phải lấy từ DB/API thật — KHÔNG suy từ spec. Actual phải lấy từ
> màn hình thật đang chạy — KHÔNG suy từ spec/design. Bắt buộc phủ ít nhất
> 1 ca biên (null/0/số dài/format đặc biệt) nếu field đó có thể rơi vào ca đó.

<!-- golden-record:start -->
| Record | Field | Expected (DB thật, viết đúng dạng hiển thị) | Actual (UI thật) | Edge case |
|--------|-------|-----------------------------------------------|-------------------|-----------|
| <property id> | <field name> | <giá trị thật từ DB, format đúng như UI nên hiển thị> | <giá trị hiển thị thật> | happy-path |
| <property id> | <field null> | <string UI NÊN hiển thị khi null, vd "—"> | <giá trị hiển thị thật> | null |
<!-- golden-record:end -->
"""


def resolve_map_path(args: argparse.Namespace) -> Path:
    if args.map:
        return Path(args.map)
    return Path(args.repo) / ".port" / f"{args.task}.goldenrecord.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="golden_record_gate",
        description=(
            "Pre-BUILD/early-verify hard block (R5/GOLD-01): verify at least "
            "one real record's Expected (real DB/API truth) and Actual "
            "(real on-screen result) are both pinned and match, for every "
            "golden-record row."
        ),
    )
    p.add_argument("--map", help="Path to the golden-record markdown file")
    p.add_argument("--repo", help="Target repo root (used together with --task)")
    p.add_argument("--task", help="Task slug (used together with --repo)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    has_map = bool(args.map)
    has_repo_task = bool(args.repo) and bool(args.task)
    has_partial_repo_task = bool(args.repo) != bool(args.task)

    if has_map and (args.repo or args.task):
        print("fail specify --map OR --repo+--task, not both", file=sys.stderr)
        return 1
    if has_partial_repo_task:
        print("fail --repo and --task must be given together", file=sys.stderr)
        return 1
    if not has_map and not has_repo_task:
        print("fail either --map or both --repo and --task are required", file=sys.stderr)
        return 1

    path = resolve_map_path(args)
    if not path.exists() or path.is_dir():
        print("fail golden-record file not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read golden-record file: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate_map(text)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
