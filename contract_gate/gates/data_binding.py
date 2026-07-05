#!/usr/bin/env python3
"""Data-binding map gate — pre-BUILD hard block for UI/migration tasks (DBIND-01, contract-gate #4).

Third sibling of `manifest_gate.py` / `greenfield_gate.py` / `coverage_gate.py`:
same stdlib-only + `pass`/`fail` prefix + exit 0/1 contract. Where the port arm
gates a Legacy Behavior Manifest and the greenfield arm gates a 2-layer oracle
spec, THIS gate closes the layer those two miss — the **data-binding layer**
(TOOL-REQUIREMENTS R4): every UI element that shows DATA must declare WHERE that
data comes from and HOW null/empty is handled, BEFORE build starts.

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

DBIND-01 (stdlib-only, hard verdict — mirrors manifest_gate.py D-01/D-03):
imports below are limited to argparse/sys/pathlib. NO third-party package, NO
.venv/pip, NO network — this must run under a bare `python3` with zero setup.
On success prints `pass <summary>` to stdout and exits 0. On any failure prints
`fail <one-line reason>` to stderr and exits 1 — the exit code + `pass`/`fail`
prefix are the load-bearing contract the SKILL.md wiring depends on.

DBIND-02 (what counts as a data-binding map): a markdown pipe table whose header
row has BOTH a column recognizable as a **type/kind** column AND a column
recognizable as a **source** column. Column position/order/count are free
(column-reorder tolerant). Multiple such tables in one file are ALL evaluated
(a real map is naturally one table per screen). At least one qualifying table
must exist, else `fail no data-binding map table found`. An optional
`<!-- data-binding:start --> ... <!-- data-binding:end -->` delimiter restricts
the scan to that block when present.

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
(?/TODO/TBD/WIP/…) counts as UNFILLED. `N/A` is NOT a placeholder — it is an
explicit, considered value (e.g. null-handling "N/A — always set by API").

DBIND-05 (DoS posture, inherited from siblings): linear line-by-line scan using
only str.split("|") — no regex, no catastrophic-backtracking surface. A
pathological >=5000-row input completes well under 1s.

Usage:
    python3 data_binding_gate.py --map <path/to/data-binding.md>
    python3 data_binding_gate.py --repo <target-repo> --task <task>
        (resolves to <target-repo>/.port/<task>.databinding.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Optional delimiter — when present, only the enclosed block is scanned.
START = "<!-- data-binding:start -->"
END = "<!-- data-binding:end -->"

# Cell counts as UNFILLED (after strip). Superset of dash look-alikes plus
# placeholder tokens that mean "haven't decided". `N/A` is intentionally NOT
# here — it is a filled, considered value.
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−"}
PLACEHOLDER_WORDS = {"todo", "tbd", "wip", "?", "??", "...", "…", "xxx", "tba"}

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
NULL_NEEDLES = (
    "null", "empty", "rỗng", "rong", "trống", "trong", "fallback",
    "nullable", "no data", "no-data",
)
FORMAT_NEEDLES = ("format", "định dạng", "dinh dang", "đơn vị", "don vi")
ELEMENT_NEEDLES = ("element", "phần tử", "phan tu", "component", "affordance")
SCREEN_NEEDLES = ("screen", "màn", "page", "trang", "view")


def _norm(cell: str) -> str:
    return cell.strip()


def _is_empty_cell(cell: str) -> bool:
    n = _norm(cell)
    return n in EMPTY_CELL_MARKERS or n.lower() in PLACEHOLDER_WORDS


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


def _is_data_type(type_cell: str) -> bool:
    """DBIND-03: a row is data-bearing unless its type cell names an explicit
    static kind (and no data kind). Unknown/empty type -> data (conservative)."""
    low = _norm(type_cell).lower()
    has_data = any(k in low for k in DATA_TYPE_KEYWORDS)
    if has_data:
        return True
    has_static = any(k in low for k in STATIC_TYPE_KEYWORDS)
    return not has_static


def _extract_scope(text: str) -> str:
    """If the optional delimiter is present, restrict to the enclosed block;
    otherwise scan the whole document."""
    i = text.find(START)
    if i < 0:
        return text
    j = text.find(END, i + len(START))
    if j < 0:
        return text[i + len(START):]
    return text[i + len(START):j]


def evaluate_map(text: str) -> tuple[bool, str]:
    """Core DBIND-02..DBIND-04 verdict over a data-binding map document.

    Returns (ok, reason). Scans every qualifying table (type + source columns)
    within scope; a data row missing a source, a data table lacking a
    null-handling column, an unfilled null cell, or (when a format column
    exists) an unfilled format cell all fail with a reason naming the offending
    screen/element. Linear single pass (DBIND-05) — no regex.
    """
    if not text or not text.strip():
        return False, "map empty"

    lines = _extract_scope(text).splitlines()
    n = len(lines)

    qualifying_tables = 0
    data_rows_total = 0

    i = 0
    while i < n:
        if not _looks_like_table_row(lines[i]):
            i += 1
            continue
        header_cells = _split_row(lines[i])
        if _is_separator_row(header_cells):
            i += 1
            continue

        # A header candidate. Does it qualify as a data-binding table?
        type_col = _find_col(header_cells, TYPE_NEEDLES)
        source_col = _find_col(header_cells, SOURCE_NEEDLES)
        if type_col is None or source_col is None:
            # Not a data-binding table — skip its whole body so unrelated
            # tables (with type-but-no-source etc.) don't false-trigger.
            i = _skip_table_body(lines, i + 1, n)
            continue

        qualifying_tables += 1
        null_col = _find_col(header_cells, NULL_NEEDLES)
        format_col = _find_col(header_cells, FORMAT_NEEDLES)
        elem_col = _find_col(header_cells, ELEMENT_NEEDLES)
        screen_col = _find_col(header_cells, SCREEN_NEEDLES)

        # Walk this table's body.
        j = i + 1
        if j < n and _looks_like_table_row(lines[j]) and _is_separator_row(_split_row(lines[j])):
            j += 1

        table_row_idx = 0
        while j < n and _looks_like_table_row(lines[j]):
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

            source_cell = cells[source_col] if source_col < len(cells) else ""
            if _is_empty_cell(source_cell):
                return False, f'data element {label} has no source (nguồn) — ô data chưa ghi nguồn = chưa cho build'

            if null_col is None:
                return False, (
                    f'data element {label} — map thiếu cột null/empty-handling '
                    f'(LAND null là bug hay trốn nhất, phải khai)'
                )
            null_cell = cells[null_col] if null_col < len(cells) else ""
            if _is_empty_cell(null_cell):
                return False, f'data element {label} has no null/empty handling'

            if format_col is not None:
                format_cell = cells[format_col] if format_col < len(cells) else ""
                if _is_empty_cell(format_cell):
                    return False, f'data element {label} has no format (điền hoặc ghi N/A)'

            j += 1

        i = j

    if qualifying_tables == 0:
        return False, (
            "no data-binding map table found "
            "(cần bảng có cột type/loại + source/nguồn — R4 Screen×Element map)"
        )

    return True, (
        f"{data_rows_total} data binding(s) verified across "
        f"{qualifying_tables} table(s) (nguồn + null-handling present)"
    )


def _skip_table_body(lines: list[str], start: int, n: int) -> int:
    """Advance past a contiguous run of table rows starting at `start`,
    returning the index of the first non-table line."""
    k = start
    while k < n and _looks_like_table_row(lines[k]):
        k += 1
    return k


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
    with BOTH a type/kind and a source column). Lets the CLI skip files that
    merely share a generic name (e.g. `*.contract.md`) but hold a different
    kind of contract — a gate should not fail a file it does not own."""
    for line in _extract_scope(text).splitlines():
        if not _looks_like_table_row(line):
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        if _find_col(cells, TYPE_NEEDLES) is not None and _find_col(cells, SOURCE_NEEDLES) is not None:
            return True
    return False


def applies(text: str) -> bool:
    return contains_binding_table(text)


def evaluate(text: str) -> tuple[bool, str]:
    return evaluate_map(text)


TEMPLATE = """\
# Data-binding map — <screen/feature>

> Screen × Element × {type; source; format; null}. List elements that carry
> DATA (+ a few static rows for contrast). Skip the 80% obvious chrome.
> A `data`-typed row with no source, or a data table that never tracks
> null/empty, fails the gate.

<!-- data-binding:start -->
| Screen | Element | Type | Source (API/field/computed) | Format | Null/empty |
|--------|---------|------|------------------------------|--------|------------|
| <screen> | <field name> | data | `GET /x` → `obj.field` | raw | "-" if null |
| <screen> | <heading>    | title |                        |        |            |
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
