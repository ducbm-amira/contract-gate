#!/usr/bin/env python3
"""Data-binding map gate — pre-BUILD hard block for UI/migration tasks (DBIND-01, contract-gate #4).

Third sibling of `manifest.py` / `greenfield.py`: same stdlib-only +
`pass`/`fail` prefix + exit 0/1 contract. Where the port arm gates a Legacy
Behavior Manifest and the greenfield arm gates a 2-layer oracle spec, THIS
gate closes the layer those two miss — the **data-binding layer**
(TOOL-REQUIREMENTS R4): every UI element that shows DATA must declare WHERE
that data comes from and HOW null/empty is handled, BEFORE build starts.

Why it exists (bằng chứng, không tưởng tượng): the two columns "Data lấy từ đâu"
and null/empty-handling are demonstrably where UI/migration bugs hide — a `sale_`
field wired to the wrong column, a LAND record whose price is null crashing the
render, a 0-usage typed field left half-ported. qa-verify and design-fidelity
are both BLIND to a wrong-source binding: the screen renders *something*, just
the wrong thing. Making "every data element has a declared source + null rule"
a runnable hard block turns that from an eyeball loop into exit≠0.

Scope discipline (DP1 — chỉ spec chỗ mù, không spec mọi thứ): the gate does NOT
demand a source for every element — 80% of a screen is static chrome the model
gets right. It gates ONLY the rows the author classified (or left unclassified)
as data-bearing. Static types (title/label/image/icon/action/state) are exempt
by design.

DBIND-01 (stdlib-only, hard verdict — mirrors manifest.py D-01/D-03):
imports below are limited to argparse/sys/pathlib plus the sibling
`contract_gate.tableparse` module (also stdlib-only). NO third-party package,
NO .venv/pip, NO network — this must run under a bare `python3` with zero
setup. On success prints `pass <summary>` to stdout and exits 0. On any
failure prints `fail <one-line reason>` to stderr and exits 1 — the exit
code + `pass`/`fail` prefix are the load-bearing contract the SKILL.md
wiring depends on.

DBIND-02 (what counts as a data-binding map): a markdown pipe table whose
header row has BOTH a column recognizable as a **type/kind** column AND a
DISTINCT column recognizable as a **source** column (mutually-exclusive
resolution via `tableparse.find_col`'s exclude set — the GOLD-06 collision
guard, ported 2026-07-11). Column position/order/count are free
(column-reorder tolerant). Multiple such tables in one file are ALL
evaluated — including tables ABUTTING each other with no blank line in
between (before, a qualifying failing table glued under a non-qualifying
one was swallowed whole by the skip-table-body scan: a demonstrated false
PASS). A qualifying table must have at least one body row (a bare header is
an ungraded claim). At least one qualifying table must exist, else `fail no
data-binding map table found`. An optional `<!-- data-binding:start -->
... <!-- data-binding:end -->` delimiter restricts the scan to those
block(s) when present — EVERY such block is scanned, not just the first.

DBIND-03 (row classification): each body row is DATA-bearing or static, decided
by its type cell:
  - contains a recognized STATIC keyword (title/label/image/icon/action/button/
    state/static/heading/nav/link/…) and NO data keyword -> static, NOT gated;
  - otherwise (a data keyword like data/computed/field/value/binding, OR an
    UNRECOGNIZED / empty type) -> treated as DATA and gated.
The unknown-type-is-data default is deliberate: a false PASS (a data element
slipping through ungated) defeats the gate's entire purpose, whereas a false
FAIL only costs the author a relabel to an explicit static type.

DBIND-04 (the gate — per data row):
  1. source cell must be non-empty and non-placeholder (ALWAYS mandatory — this
     is R4's literal gate: "ô loại data mà chưa ghi nguồn = chưa cho build");
  2. the table must HAVE a null/empty-handling column, and each data row's cell
     in it must be non-empty and non-placeholder (LAND-null is the #1 migration
     bug — a table that never even tracks null is itself the drift);
  3. IF the table has a format column, each data row's format cell must be
     non-empty and non-placeholder (format is optional to TRACK per DP1, but
     once a column exists it must be filled — bare toLocaleString / missing 万円
     is a real JP locale bug).
A cell that is whitespace-only, a lone dash look-alike, or a placeholder word
(?/TODO/TBD/WIP/…) counts as UNFILLED — the family-wide
`tableparse.is_empty_cell` rule. `N/A` is NOT a placeholder — it is an
explicit, considered value (e.g. null-handling "N/A — always set by API").

DBIND-05 (DoS posture, inherited from siblings): linear line-by-line scan,
split-based cell parsing — no regex, no catastrophic-backtracking surface. A
pathological >=5000-row input completes well under 1s.

DBIND-06 (needle hygiene, 2026-07-11): NULL_NEEDLES no longer contains the
bare Vietnamese word "trong" ("in/inside" — one of the most common VN words)
nor "rong" (a substring of English "wrong"/"strong"). Either could hijack
the null-column resolution to an always-filled column that merely mentioned
the word (e.g. "Giá trị trong DB"), so the REAL null column's empty cells
were never gated — a demonstrated false PASS. Match on
null/empty/rỗng/trống/空 (plus fallback/no-data) only; an author who types
"trong"/"rong" without diacritics gets a LOUD "map thiếu cột null" failure
and renames the header, which is the safe direction.

Usage:
    python3 -m contract_gate.gates.data_binding --map <path/to/data-binding.md>
    python3 -m contract_gate.gates.data_binding --repo <target-repo> --task <task>
        (resolves to <target-repo>/.port/<task>.databinding.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .. import tableparse as tp
except ImportError:  # standalone `python3 contract_gate/gates/data_binding.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from contract_gate import tableparse as tp

# Optional delimiter — when present, only the enclosed block(s) are scanned
# (EVERY start..end pair, not just the first — tableparse.extract_scope).
START = "<!-- data-binding:start -->"
END = "<!-- data-binding:end -->"

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

# DBIND-03 classification keywords (matched case-insensitively as substrings of
# the type/kind cell). STATIC wins only when NO data keyword is also present.
DATA_TYPE_KEYWORDS = (
    "data", "dữ liệu", "du lieu", "computed", "derived", "dynamic",
    "field", "api", "value", "giá trị", "gia tri", "binding",
)
STATIC_TYPE_KEYWORDS = (
    "title", "label", "image", "img", "icon", "action", "button", "state",
    "static", "heading", "header", "nav", "link", "decoration", "tiêu đề",
    "nhãn", "ảnh", "nút", "trạng thái", "tĩnh",
)

# Header-detection needles (lowercase substrings, EN/VN).
TYPE_NEEDLES = ("type", "kind", "loại", "loai", "phân loại", "phan loai")
SOURCE_NEEDLES = (
    "source", "nguồn", "nguon", "binding", "từ đâu", "tu dau",
    "data from", "lấy từ", "lay tu",
)
# DBIND-06: no bare "trong"/"rong" — see module docstring.
NULL_NEEDLES = (
    "null", "empty", "rỗng", "trống", "空", "fallback",
    "no data", "no-data",
)
FORMAT_NEEDLES = ("format", "định dạng", "dinh dang", "đơn vị", "don vi")
ELEMENT_NEEDLES = ("element", "phần tử", "phan tu", "component", "affordance")
SCREEN_NEEDLES = ("screen", "màn", "page", "trang", "view")
# Optional column declaring whether a data source is an EXISTING API (curl-able
# now, wire-only) or a NEW one (a BE build dependency — a cross-team blocker that
# is easy to hide). NOT the bare word "api" (that lives in the Source header).
API_NEEDLES = ("cũ/mới", "cu/moi", "existing/new", "old/new", "api status",
               "api cũ", "api moi", "api mới", "reuse", "existing?")
# A cell value that means "needs a brand-new API/endpoint the BE must build".
_NEW_API_MARKERS = ("new", "mới", "moi", "chưa có", "chua co", "build mới", "tbd-api")


def _is_data_type(type_cell: str) -> bool:
    """DBIND-03: a row is data-bearing unless its type cell names an explicit
    static kind (and no data kind). Unknown/empty type -> data (conservative)."""
    low = _norm(type_cell).lower()
    has_data = any(k in low for k in DATA_TYPE_KEYWORDS)
    if has_data:
        return True
    has_static = any(k in low for k in STATIC_TYPE_KEYWORDS)
    return not has_static


def _resolve_header(cells: list[str]) -> dict | None:
    """DBIND-02: qualify iff the header has a type/kind column AND a DISTINCT
    source column. All columns are resolved in priority order, each excluding
    indices already claimed (GOLD-06 guard) — no two fields can silently
    resolve to the same column."""
    type_col = _find_col(cells, TYPE_NEEDLES)
    if type_col is None:
        return None
    claimed = frozenset({type_col})
    source_col = _find_col(cells, SOURCE_NEEDLES, exclude=claimed)
    if source_col is None:
        return None
    claimed = claimed | {source_col}
    resolved: dict = {"type_col": type_col, "source_col": source_col}
    for key, needles in (
        ("null_col", NULL_NEEDLES),
        ("format_col", FORMAT_NEEDLES),
        ("api_col", API_NEEDLES),
        ("elem_col", ELEMENT_NEEDLES),
        ("screen_col", SCREEN_NEEDLES),
    ):
        col = _find_col(cells, needles, exclude=claimed)
        resolved[key] = col
        if col is not None:
            claimed = claimed | {col}
    return resolved


def _row_label(cells: list[str], screen_col: int | None, elem_col: int | None, idx: int) -> str:
    """Build a human-readable "screen × element" label for a failing row,
    falling back to the row index within its table."""
    screen = _norm(cells[screen_col]) if screen_col is not None and screen_col < len(cells) else ""
    elem = _norm(cells[elem_col]) if elem_col is not None and elem_col < len(cells) else ""
    if screen and elem:
        return f'"{screen} × {elem}"'
    if elem:
        return f'"{elem}"'
    if screen:
        return f'"{screen}" (row {idx})'
    return f"row {idx}"


def _analyze(text: str) -> tuple[list[str], str]:
    """Single linear pass shared by evaluate_map (fail-fast) and findings
    (collect-all). Returns (findings, summary): a non-empty findings list means
    fail; summary is meaningful only when findings is empty. No regex (DBIND-05).
    """
    if not text or not text.strip():
        return ["map empty"], ""

    lines = tp.extract_scope(text, START, END).splitlines()
    tables = tp.iter_tables(lines, _resolve_header)

    if not tables:
        return ["no data-binding map table found "
                "(cần bảng có cột type/loại + source/nguồn — R4 Screen×Element map)"], ""

    fs: list[str] = []
    data_rows_total = 0
    new_api_count = 0

    for t_idx, table in enumerate(tables):
        type_col = table["type_col"]
        source_col = table["source_col"]
        null_col = table["null_col"]
        format_col = table["format_col"]
        api_col = table["api_col"]
        elem_col = table["elem_col"]
        screen_col = table["screen_col"]
        table_label = tp.nearest_heading(lines, table["header_idx"]) or f"table {t_idx + 1}"

        table_row_idx = 0
        j = table["row_start"]
        while j < table["row_end"]:
            cells = _split_row(lines[j])
            if _is_separator_row(cells):
                j += 1
                continue
            table_row_idx += 1

            type_cell = cells[type_col] if type_col < len(cells) else ""
            if not _is_data_type(type_cell):
                j += 1
                continue

            data_rows_total += 1
            label = _row_label(cells, screen_col, elem_col, table_row_idx)

            # One finding per row: report the first issue in order, then move on.
            source_cell = cells[source_col] if source_col < len(cells) else ""
            if _is_empty_cell(source_cell):
                fs.append(f'data element {label} has no source (nguồn) — ô data chưa ghi nguồn = chưa cho build')
                j += 1
                continue

            if null_col is None:
                fs.append(
                    f'data element {label} — map thiếu cột null/empty-handling '
                    f'(LAND null là bug hay trốn nhất, phải khai)'
                )
                j += 1
                continue
            null_cell = cells[null_col] if null_col < len(cells) else ""
            if _is_empty_cell(null_cell):
                fs.append(f'data element {label} has no null/empty handling')
                j += 1
                continue

            if format_col is not None:
                format_cell = cells[format_col] if format_col < len(cells) else ""
                if _is_empty_cell(format_cell):
                    fs.append(f'data element {label} has no format (điền hoặc ghi N/A)')
                    j += 1
                    continue

            if api_col is not None:
                api_cell = cells[api_col] if api_col < len(cells) else ""
                if _is_empty_cell(api_cell):
                    fs.append(
                        f'data element {label} chưa khai API cũ/mới (existing/new) — '
                        f'new = phụ thuộc BE build, không phải wire'
                    )
                    j += 1
                    continue
                if any(m in _norm(api_cell).lower() for m in _NEW_API_MARKERS):
                    new_api_count += 1

            j += 1

        if table_row_idx == 0:
            # A bare header with zero body rows is an ungraded claim — fail
            # loudly. (Zero DATA rows among real static rows still passes:
            # nothing data-bearing to gate is a legitimate outcome, DP1.)
            fs.append(f"{table_label} has a data-binding table header but no rows")

    new_note = f"; {new_api_count} phụ thuộc API MỚI (BE build)" if new_api_count else ""
    summary = (
        f"{data_rows_total} data binding(s) verified across "
        f"{len(tables)} table(s) (nguồn + null-handling present{new_note})"
    )
    return fs, summary


def evaluate_map(text: str) -> tuple[bool, str]:
    """Core DBIND-02..DBIND-04 verdict over a data-binding map document
    (fail-fast). Returns (ok, reason) — the FIRST problem, or a pass summary.
    Delegates to _analyze; see findings() for the list-all-problems variant."""
    fs, summary = _analyze(text)
    if fs:
        return False, fs[0]
    return True, summary


def findings(text: str, path: Path | None = None) -> list[str]:
    """ALL failure reasons for a data-binding map (empty list = pass): one
    finding per problematic data row (first issue on that row), plus a per-row
    note for any data table missing a null/empty-handling column. Backs
    `contract-gate check --all`. `path` unused (no on-disk resolution)."""
    return _analyze(text)[0]


# --------------------------------------------------------------------------
# Gate descriptor — consumed by the contract-gate CLI registry. Every gate
# module exposes this same surface (KEY/TITLE/GLOBS/applies/evaluate/TEMPLATE)
# so adding a gate to the CLI is a one-line registry append.
# --------------------------------------------------------------------------

KEY = "data-binding"
TITLE = "Data-binding map"
# Filename conventions the CLI's `check` autodiscovers (agnix-style zero-config).
GLOBS = ("*.databinding.md", "*.contract.md", "*DATA-BINDING*.md", "*data-binding*.md")


def contains_binding_table(text: str) -> bool:
    """True iff `text` has at least one qualifying data-binding table (a header
    with BOTH a type/kind and a DISTINCT source column). Lets the CLI skip
    files that merely share a generic name (e.g. `*.contract.md`) but hold a
    different kind of contract — a gate should not fail a file it does not
    own. Uses the SAME header resolver as grading (no drift)."""
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
    return contains_binding_table(text)


def evaluate(text: str, path: Path | None = None) -> tuple[bool, str]:
    # path unused — data-binding needs no on-disk resolution.
    return evaluate_map(text)


DRAFT_GUIDANCE = """\
Draft a Data-binding map. List every UI element that carries DATA (plus a few
static rows — title/label/image/action — for contrast); SKIP the obvious 80%
chrome (DP1: spec only the blind spots).

For each `data` row you MUST fill:
- Source: an API path + field (`GET /owner/:id → owner.name`), a plain field
  path (`sale.price`), or `computed: <expr>`.
- Null/empty: what the UI shows when the value is null/empty/0.
- Format: only if you added a Format column.
- API cũ/mới: if you added that column, mark each data source `existing` (an API
  that already exists — you can curl it now, wire-only) or `new` (an endpoint the
  BE must still build — a cross-team dependency, not just wiring). `new` = a
  scheduling risk that must be visible, so never hide it as `existing`.

CRITICAL — do NOT game the gate: if you cannot determine a source from the
material, open the cell with `?` (a short reason after it is welcome, e.g.
`? endpoint not in spec`). NEVER invent an endpoint or field name to make the
gate pass — a leading `?` is correct; the gate fails on it so a human resolves
the real blind spot. Same for a null rule you can't infer.

Output ONLY the completed markdown contract below (keep the table shape); no
prose before or after."""


TEMPLATE = """\
# Data-binding map — <screen/feature>

> Screen × Element × {type; source; format; null}. List elements that carry
> DATA (+ a few static rows for contrast). Skip the 80% obvious chrome.
> A `data`-typed row with no source, or a data table that never tracks
> null/empty, fails the gate.

<!-- data-binding:start -->
| Screen | Element | Type | Source (API/field/computed) | API cũ/mới | Format | Null/empty |
|--------|---------|------|------------------------------|-----------|--------|------------|
| <screen> | <field name> | data | <GET /x → obj.field> | <existing hay new> | <raw / 万円> | <"-" nếu null> |
| <screen> | <field cần BE> | data | <POST /new-endpoint → y> | new | <raw> | <"-" nếu null> |
| <screen> | <heading>    | title |                        |           |        |            |
<!-- data-binding:end -->
"""


def resolve_map_path(args: argparse.Namespace) -> Path:
    if args.map:
        return Path(args.map)
    return Path(args.repo) / ".port" / f"{args.task}.databinding.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="data_binding_gate",
        description=(
            "Pre-BUILD hard block (R4/DBIND-01): verify the Screen×Element "
            "data-binding map is authored and every data element declares a "
            "source (nguồn) plus null/empty handling before build starts."
        ),
    )
    p.add_argument("--map", help="Path to the data-binding map markdown file")
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
        print("fail data-binding map not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read map: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate_map(text)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
