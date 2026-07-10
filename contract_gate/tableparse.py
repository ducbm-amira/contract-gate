#!/usr/bin/env python3
"""Shared markdown pipe-table parsing for ALL contract-gate gates.

This module is the single source of truth for the helpers that were
previously copy-pasted (and drifting) across the six gate modules:

- the UNFILLED-cell rule (`is_empty_cell`): dash look-alikes, placeholder
  words (?/TODO/TBD/WIP/…), a leading `?` ("open question, reason may
  follow"), TODO-style prefixes, and whole-cell `<angle-bracket>` scaffold
  placeholders. Before centralization, manifest.py and greenfield.py only
  checked dash look-alikes — an Observable cell of literally `TODO` or `?`
  passed both gates (a false PASS; found in the 2026-07-11 review).
- `split_row`: cell splitting that honors the markdown `\\|` escape and
  pipes inside `backtick code spans` (a raw `str.split("|")` shifted every
  column after such a cell, which let an EMPTY gated cell read a filled
  neighbor — another false PASS). NOTE: strict GFM only protects `\\|`, not
  code-span pipes; we deliberately also protect balanced code spans because
  contract cells routinely hold things like `` `GET /x?a=1|2` `` and the
  author's intent is one cell. Rows with an UNBALANCED backtick count fall
  back to treating backticks as plain characters.
- `find_col` with an `exclude` set — the GOLD-06 header-needle-collision
  guard, now available to every gate (before, only golden_record.py had it;
  testgen/greenfield could resolve two required fields to the SAME column,
  e.g. a lone "Expected behavior" header satisfying both Requirement and
  Expected — a false PASS).
- `iter_tables`: locate EVERY qualifying table in a file, including tables
  ABUTTING each other with no blank line in between (the residue of the
  D-07 bug class: the old per-gate scanners consumed an abutting table's
  header+rows as body rows of the previous table, grading them under the
  wrong column indices — demonstrated false PASS). A row is treated as a
  new header candidate iff it starts a table block OR is immediately
  followed by a separator row (`|---|---|`), which is how real markdown
  headers are written; body rows that merely contain needle words are
  therefore never mistaken for headers.
- `extract_scope`: honor EVERY `<!-- x:start --> … <!-- x:end -->` marker
  block in a file, not just the first (a failing table in a second block
  used to be invisible — false PASS).

Stdlib-only, no regex (the linear, split-based scan is the gates' shared
DoS posture: no catastrophic-backtracking surface).
"""
from __future__ import annotations

# Whitespace-only (after strip -> "") or a lone dash/prolonged-sound-mark/minus
# counts as an empty cell. Superset of common dash look-alikes.
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−"}
# Whole-cell tokens that mean "haven't decided". `N/A` is intentionally NOT
# here — it is a filled, considered value (e.g. "N/A — always set by API").
PLACEHOLDER_WORDS = {"todo", "tbd", "wip", "?", "??", "...", "…", "xxx", "tba"}
# Placeholder tokens that mark a cell UNRESOLVED when they OPEN the cell —
# an agent/human naturally annotates the gap (`TODO: ask`), which is more
# useful than a bare marker but must still fail.
UNRESOLVED_PREFIXES = ("todo", "tbd", "wip", "tba")


def norm(cell: str) -> str:
    return cell.strip()


def is_empty_cell(cell: str) -> bool:
    """True iff the cell counts as UNFILLED under the family-wide rule:
    dash look-alikes, placeholder words, a leading `?` (the canonical "open
    question" — a mid-string `?` like `GET /x?id=1` is fine), TODO-style
    prefixes, and a whole-cell `<scaffold placeholder>` (exactly one `<...>`
    pair spanning the entire cell — the shape `contract-gate init` templates
    use, so an unfilled scaffold fails loudly instead of passing)."""
    n = norm(cell)
    if n in EMPTY_CELL_MARKERS:
        return True
    low = n.lower()
    if low in PLACEHOLDER_WORDS:
        return True
    if n.startswith("?"):
        return True
    if (
        len(n) >= 2
        and n.startswith("<")
        and n.endswith(">")
        and n.count("<") == 1
        and n.count(">") == 1
    ):
        return True
    for w in UNRESOLVED_PREFIXES:
        if low == w or low.startswith(w + " ") or low.startswith(w + ":") or low.startswith(w + "-"):
            return True
    return False


def looks_like_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def split_row(line: str) -> list[str]:
    """Split a markdown pipe-table row into cells (format-forgiving:
    leading/trailing pipe optional, no column-count validation). Honors the
    `\\|` escape and pipes inside balanced `backtick code spans` — see the
    module docstring for why. Fast path: rows without escapes/backticks use
    a plain split."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]

    if "\\|" not in s and "`" not in s:
        if s.endswith("|"):
            s = s[:-1]
        return [c.strip() for c in s.split("|")]

    honor_code_spans = s.count("`") % 2 == 0
    cells: list[str] = []
    buf: list[str] = []
    in_code = False
    k = 0
    length = len(s)
    while k < length:
        ch = s[k]
        if ch == "\\" and k + 1 < length and s[k + 1] == "|":
            buf.append("|")
            k += 2
            continue
        if ch == "`" and honor_code_spans:
            in_code = not in_code
            buf.append(ch)
            k += 1
            continue
        if ch == "|" and not in_code:
            cells.append("".join(buf))
            buf = []
            k += 1
            continue
        buf.append(ch)
        k += 1
    cells.append("".join(buf))
    # A trailing pipe produces one empty final chunk — drop it (mirrors the
    # fast path's trailing-pipe strip, keeps genuinely-empty middle cells).
    if len(cells) > 1 and cells[-1].strip() == "":
        cells.pop()
    return [c.strip() for c in cells]


def is_separator_row(cells: list[str]) -> bool:
    """The markdown alignment row, e.g. `|---|:---:|---|` — every non-blank
    cell contains only '-', ':', or whitespace."""
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


def find_col(
    header_cells: list[str], needles: tuple[str, ...], exclude: frozenset = frozenset()
) -> "int | None":
    """First column whose header contains any needle (case-insensitive
    substring), skipping indices already claimed by another field — the
    GOLD-06 collision guard: two fields can never silently resolve to the
    same column when their needle lists share a substring."""
    for i, cell in enumerate(header_cells):
        if i in exclude:
            continue
        low = cell.lower()
        if any(needle in low for needle in needles):
            return i
    return None


def nearest_heading(lines: list[str], idx: int) -> "str | None":
    """Label a table by the nearest preceding markdown heading (`#`..`######`
    + text) above line `idx`, stripped of the leading `#`s. None if nothing
    precedes it."""
    i = idx - 1
    while i >= 0:
        s = lines[i].strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        i -= 1
    return None


def _is_header_candidate_followed_by_sep(lines: list[str], idx: int) -> bool:
    j = idx + 1
    return (
        j < len(lines)
        and looks_like_table_row(lines[j])
        and is_separator_row(split_row(lines[j]))
    )


def iter_tables(lines: list[str], resolve_header) -> list[dict]:
    """Locate EVERY qualifying table in `lines`, including tables that abut
    each other with no blank line in between.

    `resolve_header(header_cells) -> dict | None` is the gate's own column
    resolution: a dict of resolved column indices qualifies the table, None
    rejects it. Each returned descriptor carries the resolved fields plus
    `header_idx`, `header_cells`, and the [row_start, row_end) line range of
    its body rows.

    Header-candidate rule: a non-separator table row is considered a header
    iff it STARTS a table block (previous line is not a table row) OR it is
    immediately followed by a separator row. Real markdown headers always
    satisfy one of these; body rows that merely contain needle words satisfy
    neither, so they are never misread as headers. A body row that does
    start an abutting table (followed by a separator AND resolving as a
    qualifying header) ends the previous table's body right there — before
    this, an abutting table's rows were graded under the PREVIOUS table's
    column indices (false-PASS surface). Known residual limit: a qualifying
    table with NO separator row glued directly under another table is still
    consumed as body rows (real markdown tables have separators).

    Linear single pass; no regex.
    """
    n = len(lines)
    tables: list[dict] = []
    i = 0
    prev_is_table_row = False
    while i < n:
        line = lines[i]
        if not looks_like_table_row(line):
            prev_is_table_row = False
            i += 1
            continue
        cells = split_row(line)
        if is_separator_row(cells):
            prev_is_table_row = True
            i += 1
            continue
        next_is_sep = _is_header_candidate_followed_by_sep(lines, i)
        if not prev_is_table_row or next_is_sep:
            resolved = resolve_header(cells)
            if resolved is not None:
                j = i + 1 + (1 if next_is_sep else 0)
                row_start = j
                while j < n and looks_like_table_row(lines[j]):
                    bcells = split_row(lines[j])
                    if (
                        not is_separator_row(bcells)
                        and _is_header_candidate_followed_by_sep(lines, j)
                        and resolve_header(bcells) is not None
                    ):
                        break  # header of an abutting qualifying table
                    j += 1
                table = dict(resolved)
                table["header_idx"] = i
                table["header_cells"] = cells
                table["row_start"] = row_start
                table["row_end"] = j
                tables.append(table)
                i = j
                prev_is_table_row = True
                continue
        prev_is_table_row = True
        i += 1
    return tables


def extract_scope(text: str, start_marker: str, end_marker: str) -> str:
    """When at least one `start_marker` is present, return the concatenation
    of EVERY start..end block (an unterminated final block runs to EOF);
    otherwise return the whole text. Before centralization only the FIRST
    block was scanned — a failing table in a second block was invisible."""
    i = text.find(start_marker)
    if i < 0:
        return text
    parts: list[str] = []
    while i >= 0:
        i += len(start_marker)
        j = text.find(end_marker, i)
        if j < 0:
            parts.append(text[i:])
            break
        parts.append(text[i:j])
        i = text.find(start_marker, j + len(end_marker))
    return "\n".join(parts)
