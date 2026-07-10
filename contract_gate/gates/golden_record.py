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
imports below are limited to argparse/sys/pathlib plus the sibling
`contract_gate.tableparse` module (also stdlib-only). NO third-party
package, NO network, NO DB driver — this gate NEVER queries a database or
drives a browser itself (that would break the zero-dep/agent-agnostic
contract and also just relocate the "trust me" problem). It only gates a
markdown artifact where a human/agent has ALREADY pinned the real answer
and the real on-screen result side by side. On success prints
`pass <summary>` to stdout and exits 0; on failure prints
`fail <one-line reason>` to stderr and exits 1.

GOLD-02 (what counts as a golden-record table): a markdown pipe table whose
header row has BOTH a column recognizable as **Expected** (the real DB/API
truth) AND a DISTINCT column recognizable as **Actual** (what the running
app really displayed). Record/Field columns are optional but used for the
failure label when present. Column order/count is free (reorder-tolerant),
multiple qualifying tables in one file are all evaluated — including tables
abutting each other with no blank line in between. A qualifying table must
have at least one body row (fixed 2026-07-11; before, a bare header passed
with "0 golden record(s) verified" — trivially gameable). An optional
`<!-- golden-record:start --> ... <!-- golden-record:end -->` delimiter
restricts the scan to those block(s) — EVERY such block is scanned, not
just the first.

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
word (?/TODO/TBD/WIP/…) counts as UNFILLED — the family-wide
`tableparse.is_empty_cell` rule (including the leading-`?`-with-reason
case), now genuinely identical across the gate family because it IS the
same function.

GOLD-04 (DoS posture, inherited from siblings): linear line-by-line scan,
split-based cell parsing — no regex, no catastrophic-backtracking surface.

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
earlier field, letting expected_col and actual_col silently resolve to the
SAME column (comparing Expected against itself — a false PASS). The exclude
guard now lives in `tableparse.find_col` and is used by the whole family.

GOLD-06b (resolution priority, 2026-07-11): the Record/ID column is resolved
FIRST, then Expected excluding it, then Actual excluding both. Reason:
EXPECTED_NEEDLES contains "golden", and the most natural header for this
file type — `| Golden record | Field | Expected | Actual |` — used to
hijack expected_col to the ID column (Expected was then compared against
the real Actual: every row failed with a nonsense "P-123 != ¥100" mismatch,
a false FAIL on a perfectly good table). Record-first resolution keeps both
the natural header AND the template header resolving correctly.

GOLD-07 (GLOBS narrowed, no bare-substring catch-all — mirrors manifest.py/
greenfield.py, and the same fix later applied to fidelity.py's FID-08/
testgen.py's RTM-07): only the suffix-anchored `*.goldenrecord.md` /
`*.golden-record.md` are matched — a real golden-record file must be named
`<screen>.goldenrecord.md` or `<screen>.golden-record.md` (the init
scaffold is `example.golden-record.md`, which the GLOBS DO match — an
unfilled scaffold fails loudly instead of hiding under a name no gate owns).

Usage:
    python3 -m contract_gate.gates.golden_record --map <path/to/golden-record.md>
    python3 -m contract_gate.gates.golden_record --repo <target-repo> --task <task>
        (resolves to <target-repo>/.port/<task>.goldenrecord.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .. import tableparse as tp
except ImportError:  # standalone `python3 contract_gate/gates/golden_record.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from contract_gate import tableparse as tp

# Optional delimiter — when present, only the enclosed block(s) are scanned.
START = "<!-- golden-record:start -->"
END = "<!-- golden-record:end -->"

# Shared family-wide helpers (see tableparse.py). Local aliases keep the
# historical names used throughout this module.
EMPTY_CELL_MARKERS = tp.EMPTY_CELL_MARKERS
PLACEHOLDER_WORDS = tp.PLACEHOLDER_WORDS
_UNRESOLVED_PREFIXES = tp.UNRESOLVED_PREFIXES
_norm = tp.norm
_is_empty_cell = tp.is_empty_cell
_looks_like_table_row = tp.looks_like_table_row
_split_row = tp.split_row
_is_separator_row = tp.is_separator_row
_find_col = tp.find_col

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


def _resolve_header(cells: list[str]) -> dict | None:
    """GOLD-02/GOLD-06/GOLD-06b: qualify iff the header has an Expected AND a
    DISTINCT Actual column. Resolution order: record (so a "Golden record"
    ID column can't hijack Expected) -> expected -> actual -> field -> edge,
    each excluding indices already claimed."""
    record_col = _find_col(cells, RECORD_NEEDLES)
    claimed = frozenset() if record_col is None else frozenset({record_col})
    expected_col = _find_col(cells, EXPECTED_NEEDLES, exclude=claimed)
    if expected_col is None:
        return None
    claimed = claimed | {expected_col}
    actual_col = _find_col(cells, ACTUAL_NEEDLES, exclude=claimed)
    if actual_col is None:
        return None
    claimed = claimed | {actual_col}
    field_col = _find_col(cells, FIELD_NEEDLES, exclude=claimed)
    if field_col is not None:
        claimed = claimed | {field_col}
    return {
        "record_col": record_col,
        "field_col": field_col,
        "expected_col": expected_col,
        "actual_col": actual_col,
        "edge_col": _find_col(cells, EDGECASE_NEEDLES, exclude=claimed),
    }


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


def _analyze(text: str) -> tuple[list[str], str]:
    """Single linear pass backing both evaluate() (fail-fast) and findings()
    (collect-all). Returns (findings, summary): non-empty findings = fail."""
    if not text or not text.strip():
        return ["golden-record file empty"], ""

    lines = tp.extract_scope(text, START, END).splitlines()
    tables = tp.iter_tables(lines, _resolve_header)

    if not tables:
        return [
            "no golden-record table found "
            "(cần bảng có cột Expected + Actual — R5 2-column oracle)"
        ], ""

    fs: list[str] = []
    rows_total = 0

    for t_idx, table in enumerate(tables):
        record_col = table["record_col"]
        field_col = table["field_col"]
        expected_col = table["expected_col"]
        actual_col = table["actual_col"]
        edge_col = table["edge_col"]
        table_label = tp.nearest_heading(lines, table["header_idx"]) or f"table {t_idx + 1}"

        row_idx = 0
        j = table["row_start"]
        while j < table["row_end"]:
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

        if row_idx == 0:
            # GOLD-02: a bare header with zero body rows is an ungraded
            # claim, not a pass ("0 verified" used to read as success).
            fs.append(f"{table_label} has a golden-record table header but no rows")

    summary = f"{rows_total} golden record(s) verified against real DB/UI truth across {len(tables)} table(s)"
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
    """True iff `text` has at least one qualifying table (a header with BOTH
    an Expected and a DISTINCT Actual column) — lets the CLI skip files that
    merely share a generic name but hold a different kind of contract. Uses
    the SAME header resolver as grading (no drift)."""
    for line in tp.extract_scope(text, START, END).splitlines():
        if not _looks_like_table_row(line):
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        if _resolve_header(cells) is not None:
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
