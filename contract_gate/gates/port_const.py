#!/usr/bin/env python3
"""Port-constant diff gate — advisory data-CORRECTNESS check for a Vue->React
port's literal VALUES (PCONST-01, "check 2" of the design-fidelity effort,
contract-gate gate #7).

Sixth sibling of `data_binding.py` / `golden_record.py` / `manifest.py` /
`greenfield.py` / `fidelity.py` / `testgen.py`: same stdlib-only +
`pass`/`fail` prefix + exit 0/1 contract. Where `golden_record` verifies a
DATA VALUE against real DB/UI truth, and `data_binding` verifies a data
element DECLARES a source, THIS gate closes a third, distinct hole: a
PORTED constant/literal (a dropdown option list, an enum, a business-rule
string) that silently DRIFTS from its own source repo during the port —
no query against reality is needed here, only a diff of the SAME literal
against itself across two repos/files. No existing gate in this family
diffs literal VALUES between a source repo and a built repo.

Real bug classes this exists to catch (bằng chứng, không tưởng tượng): a
種類 (kind) dropdown that silently lost 10 北海道 (Hokkaido) region entries
during a Vue->React port; a sort/comparator list whose element order was
reshuffled. Both are invisible to qa-verify (the screen renders *a*
dropdown, just with fewer/reordered options) and invisible to
`golden_record` (no single record's Expected/Actual disagrees — the whole
LIST itself quietly shrank).

PCONST-01 (stdlib-only, hard verdict — mirrors data_binding.py's DBIND-01):
imports below are limited to argparse/sys/pathlib plus the sibling
`contract_gate.tableparse` module (also stdlib-only). NO third-party
package, NO network, NO AST/parser library for the source files being
diffed — see PCONST-04 for why a bespoke bounded scanner is used instead of
importing a real JS/TS parser. On success prints `pass <summary>` to
stdout and exits 0; on failure prints `fail <one-line reason>` to stderr
and exits 1.

PCONST-02 (what counts as a port-const table): a markdown pipe table whose
header row has a DISTINCT column recognizable as **Source** AND a DISTINCT
column recognizable as **Built** (mutually-exclusive resolution via
`tableparse.find_col`'s exclude set — the GOLD-06 collision guard, same
discipline as every sibling). A Constant/label column and a Kind column are
both OPTIONAL — exactly like `golden_record`'s optional Record/Field/
Edge-case columns: present or not, they never affect table QUALIFICATION,
only row labeling / extraction mode. Column order/count is free
(reorder-tolerant); multiple qualifying tables in one file are ALL
evaluated, including tables abutting each other with no blank line between
(`tableparse.iter_tables` handles this — see its docstring). An optional
`<!-- port-const:start --> ... <!-- port-const:end -->` delimiter restricts
the scan to those block(s) when present — every such block is scanned. A
qualifying table must have at least one body row (a bare header is an
ungraded claim, mirrors DBIND-02/GOLD-02's F7 fix).

PCONST-03 (the gate — per data row, in order):
  1. Each of Source/Built must parse as `<filepath>#<identifier>` (a `#`
     splits the two halves; both halves non-blank after stripping). A cell
     that is blank, a placeholder (`?`/TODO/...), or missing the `#`
     entirely is a MALFORMED locator -> row fails loudly. This is the same
     "loud-over-silent" posture as `data_binding`'s DBIND-04.1: an unfilled
     locator must never look like a silent pass.
  2. Both declared files are resolved (PCONST-05) and read. A file that
     does not exist, is a directory, or cannot be decoded -> row fails
     naming which side (source/built) and the resolved path. A gate this
     advisory-tier NEVER lets an unreadable declared file pass silently —
     that would defeat the entire "check the drift really happened" point.
  3. The identifier is extracted from each file per PCONST-04. If EITHER
     side returns None (identifier not found in that file — distinct from
     "found but empty"), the row fails naming the locator and file.
  4. If both sides parsed to a non-None set and the sets differ, the row
     fails naming the constant plus the SYMMETRIC difference: values in
     Source but MISSING from Built, and values in Built but EXTRA (not in
     Source), reported separately and capped to a few items each (PCONST-06)
     so a 200-entry drift doesn't flood the terminal.
  5. Equal sets -> row passes (counted toward the summary).
A table with zero data rows scanned (bare header) fails loudly, same as
every sibling's "0 verified" F7 fix.

PCONST-04 (literal extraction — the novel core of this gate, STDLIB ONLY,
NO regex): `extract_literal_set(file_text, locator, kind)` finds the FIRST
occurrence of `locator` as a STANDALONE identifier (not a substring of a
longer name — boundary-checked on both sides) immediately followed
(whitespace-tolerant) by `=` or `:` (an assignment or an object-literal key
— covers both `export const X = [...]` and `X: [...]` inside an enum
object), skipping `===`/`==` so a comparison expression is never mistaken
for a declaration. From there:
  - `kind=scalar`: the RHS token up to the first top-level `;` or newline,
    quotes/whitespace stripped -> a 1-element set.
  - `kind=list` (the default): skip whitespace to the first `[` or `{`.
    - `[...]`: DEPTH-COUNT brackets (tracking `'`/`"`/`` ` `` quoted spans so
      a `]` inside a string element never closes the array early — the
      priority case, e.g. the 北海道 array-of-strings bug this gate exists
      to catch) and split the inner region at TOP-LEVEL commas (also
      quote/nesting-aware) -> each element stripped of quotes/whitespace.
    - `{...}` (an enum object literal): same depth-count on braces, but each
      top-level entry is split at its first top-level `:` and the KEY half
      is kept (DESIGN CHOICE, documented here since the alternative — VALUES
      — is equally defensible: an enum's KEY is the stable, human-authored
      name a port is most likely to accidentally drop/rename, whereas the
      VALUE is often a derived/formatted string. Both sides of a diff use
      the same rule, so the comparison stays internally consistent either
      way; keys were picked for readability of the resulting diff).
  - Returns `None` if the identifier is not found at all (distinct from a
    found-but-empty set) — a `None` on EITHER side fails that row.

PCONST-05 (file path resolution): the `<filepath>` half of a locator cell
is used AS-IS if absolute; otherwise it is resolved relative to the
CONTRACT file's own directory (`path.parent`, where `path` is the Path the
CLI/`evaluate()` was given). Source and built files routinely live in
DIFFERENT repos, so an absolute path is the common case here — both forms
are supported. When `evaluate()`/`findings()` are called with `path=None`
(e.g. a unit test exercising the parser directly with no on-disk contract
file), a relative locator cell is resolved relative to the current working
directory as a best-effort fallback; an absolute locator cell is
unaffected either way.

PCONST-06 (DoS posture, inherited from siblings + a bespoke bound for the
extractor): the table scan itself is the family's usual linear/split-based
scan (no regex). The NEW surface — scanning arbitrary source/built files —
adds its own bound: the identifier search is a single left-to-right pass
(no repeated whole-file re-scans), and the balanced-bracket scan is capped
at `_MAX_SCAN` (100k) chars from the opening bracket; an unbalanced/
pathological region past that cap returns None (treated as "locator not
found") rather than scanning unbounded. Symmetric-difference findings are
capped to `_DIFF_CAP` items per side.

PCONST-07 (advisory-first, NOT a hard block — BACKLOG discipline): this
gate returns pass/fail exactly like every sibling and is registered in
`gates/__init__.py::REGISTRY`, so it runs under the existing advisory
`contract-gate check` tier. It does NOT modify any pinrich-cycle SKILL.md
and is NOT wired as a hard pre-BUILD block anywhere — noise on real
port-const contracts has not been measured yet. Promote it to a hard gate
only after that measurement, per the same discipline `data_binding`/
`golden_record` were promoted under.

PCONST-08 (GLOBS narrowed, no bare-substring catch-all — mirrors
golden_record.py's GOLD-07): only the suffix-anchored `*.portconst.md` /
`*.port-const.md` are matched.

Usage:
    python3 -m contract_gate.gates.port_const --map <path/to/x.portconst.md>
    python3 -m contract_gate.gates.port_const --repo <target-repo> --task <task>
        (resolves to <target-repo>/.port/<task>.portconst.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .. import tableparse as tp
except ImportError:  # standalone `python3 contract_gate/gates/port_const.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from contract_gate import tableparse as tp

# Optional delimiter — when present, only the enclosed block(s) are scanned.
START = "<!-- port-const:start -->"
END = "<!-- port-const:end -->"

# Shared family-wide helpers (see tableparse.py). Local aliases keep the
# historical names used throughout this module.
_norm = tp.norm
_is_separator_row = tp.is_separator_row
_looks_like_table_row = tp.looks_like_table_row
_split_row = tp.split_row
_find_col = tp.find_col

# Header-detection needles (lowercase substrings, EN/VN) — exactly the
# needle lists specified for this gate; see PCONST-02.
LABEL_NEEDLES = ("constant", "const", "label", "tên", "name", "symbol")
SOURCE_NEEDLES = ("source", "nguồn", "nguon", "gốc", "legacy", "from")
BUILT_NEEDLES = ("built", "dựng", "react", "target", "to", "ported")
KIND_NEEDLES = ("kind", "loại", "type")

# PCONST-06 bounds.
_MAX_SCAN = 100_000       # cap on the balanced-bracket scan region
_LOOKAHEAD_CAP = 500      # cap on whitespace-skip to the opening bracket
_SCALAR_CAP = 2_000       # cap on a scalar RHS token scan
_DIFF_CAP = 5             # max items shown per side of a symmetric diff

_QUOTE_CHARS = "'\"`"
_OPEN_CHARS = "[{("
_CLOSE_CHARS = "]})"


# --------------------------------------------------------------------------
# Header resolution (PCONST-02) — mirrors golden_record._resolve_header's
# priority-ordered, exclude-set collision guard (GOLD-06/06b).
# --------------------------------------------------------------------------

def _resolve_header(cells: list[str]) -> dict | None:
    """Qualify iff the header has a DISTINCT Source column AND a DISTINCT
    Built column. Label/Kind are optional and never gate qualification —
    like `golden_record`'s optional Record/Field/Edge-case columns.
    Resolution order: label (so it can't be silently hijacked later) ->
    source -> built -> kind, each excluding indices already claimed."""
    label_col = _find_col(cells, LABEL_NEEDLES)
    claimed = frozenset() if label_col is None else frozenset({label_col})
    source_col = _find_col(cells, SOURCE_NEEDLES, exclude=claimed)
    if source_col is None:
        return None
    claimed = claimed | {source_col}
    built_col = _find_col(cells, BUILT_NEEDLES, exclude=claimed)
    if built_col is None:
        return None
    claimed = claimed | {built_col}
    kind_col = _find_col(cells, KIND_NEEDLES, exclude=claimed)
    return {
        "label_col": label_col,
        "source_col": source_col,
        "built_col": built_col,
        "kind_col": kind_col,
    }


def _row_label(cells: list[str], label_col: int | None, idx: int) -> str:
    label = _norm(cells[label_col]) if label_col is not None and label_col < len(cells) else ""
    return f'"{label}"' if label else f"row {idx}"


# --------------------------------------------------------------------------
# Locator-cell parsing + file resolution (PCONST-03.1/PCONST-05).
# --------------------------------------------------------------------------

def _strip_code_span(s: str) -> str:
    """Drop a single pair of surrounding backticks (authors routinely write
    locator cells as `` `path#IDENT` `` code spans)."""
    if len(s) >= 2 and s.startswith("`") and s.endswith("`"):
        return s[1:-1].strip()
    return s


def _parse_locator_cell(cell: str) -> "tuple[str, str] | None":
    """Split a `<filepath>#<identifier>` cell. None if there is no `#`, or
    either half is blank after stripping — a blank/placeholder cell (no `#`
    at all) naturally falls into this MALFORMED case, so it fails loudly
    rather than silently passing (PCONST-03.1)."""
    c = _strip_code_span(_norm(cell))
    if "#" not in c:
        return None
    fp, _, loc = c.partition("#")
    fp = fp.strip()
    loc = loc.strip()
    if not fp or not loc:
        return None
    return fp, loc


def _resolve_file_path(cell_path: str, contract_path: "Path | None") -> Path:
    """Absolute -> as-is; otherwise relative to the CONTRACT file's own
    directory (PCONST-05). No contract path known (path=None) -> best-effort
    relative-to-CWD fallback."""
    p = Path(cell_path)
    if p.is_absolute():
        return p
    if contract_path is not None:
        return contract_path.parent / p
    return p


def _read_declared_file(path_str: str, contract_path: "Path | None") -> "tuple[str | None, str | None]":
    """Resolve + read a declared source/built file. Returns (text, error);
    a non-None error means the row must FAIL — an unreadable declared file
    is never a silent pass (loud-over-silent, per the PROJECT constraint)."""
    resolved = _resolve_file_path(path_str, contract_path)
    if not resolved.exists() or resolved.is_dir():
        return None, f"file not found: {resolved}"
    try:
        return resolved.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, f"could not read {resolved}: {e}"


# --------------------------------------------------------------------------
# Literal extraction (PCONST-04) — the novel core. Stdlib only, no regex,
# linear/bounded scans (PCONST-06).
# --------------------------------------------------------------------------

def _find_identifier_assignment(text: str, locator: str) -> "int | None":
    """Locate `locator` as a STANDALONE identifier (boundary-checked so it
    is never a substring of a longer name) immediately followed
    (whitespace-tolerant) by `=` or `:`, skipping `==`/`===` (a comparison,
    not a declaration). Returns the index right AFTER the operator, or None
    if no such occurrence exists. Single left-to-right pass — no repeated
    whole-text re-scans, so this stays linear even on adversarial input."""
    n = len(text)
    loc_len = len(locator)
    if loc_len == 0:
        return None
    i = 0
    limit = n - loc_len
    while i <= limit:
        if text[i] == locator[0] and text.startswith(locator, i):
            end = i + loc_len
            left_ok = i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")
            right_ok = end >= n or not (text[end].isalnum() or text[end] == "_")
            if left_ok and right_ok:
                k = end
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k] in "=:":
                    if text[k] == "=" and k + 1 < n and text[k + 1] == "=":
                        i += 1
                        continue
                    return k + 1
        i += 1
    return None


def _skip_ws(text: str, i: int, cap: int) -> int:
    n = len(text)
    limit = min(n, i + cap)
    while i < limit and text[i].isspace():
        i += 1
    return i


def _scan_balanced(text: str, open_ch: str, close_ch: str, start: int) -> "tuple[int, int] | None":
    """Depth-count `open_ch`/`close_ch` starting at `text[start]` (assumed
    to BE `open_ch`), skipping quoted spans (`'`/`"`/`` ` ``, backslash-
    escape aware) so a bracket char inside a string element never closes
    the region early. Bounded to `_MAX_SCAN` chars — an unbalanced/
    pathological region past that cap returns None rather than scanning
    unbounded (PCONST-06)."""
    n = len(text)
    cap_end = min(n, start + _MAX_SCAN)
    depth = 0
    i = start
    quote: "str | None" = None
    while i < cap_end:
        ch = text[i]
        if quote:
            if ch == "\\" and i + 1 < cap_end:
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in _QUOTE_CHARS:
            quote = ch
            i += 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return start, i
        i += 1
    return None


def _split_top_level(inner: str) -> list[str]:
    """Split `inner` at TOP-LEVEL commas — quote-aware (a comma inside a
    string never splits) and nesting-aware (a comma inside a nested
    `[]`/`{}`/`()` never splits either)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: "str | None" = None
    n = len(inner)
    i = 0
    while i < n:
        ch = inner[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(inner[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in _QUOTE_CHARS:
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch in _OPEN_CHARS:
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch in _CLOSE_CHARS:
            depth -= 1
            buf.append(ch)
            i += 1
            continue
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _split_key(pair: str) -> str:
    """First top-level `:` in one object-literal entry splits key from
    value; returns the KEY half (quote/nesting-aware, same rule as
    `_split_top_level`). No top-level `:` found -> the whole entry (rare;
    treated as its own key)."""
    depth = 0
    quote: "str | None" = None
    n = len(pair)
    i = 0
    while i < n:
        ch = pair[i]
        if quote:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in _QUOTE_CHARS:
            quote = ch
            i += 1
            continue
        if ch in _OPEN_CHARS:
            depth += 1
        elif ch in _CLOSE_CHARS:
            depth -= 1
        elif ch == ":" and depth == 0:
            return pair[:i]
        i += 1
    return pair


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in _QUOTE_CHARS:
        return s[1:-1]
    return s


def _extract_scalar(text: str, rhs_start: int) -> "set[str] | None":
    """kind=scalar: the RHS token up to the first top-level `;` or newline,
    trailing comma/quotes/whitespace stripped -> a 1-element set."""
    n = len(text)
    cap_end = min(n, rhs_start + _SCALAR_CAP)
    i = rhs_start
    while i < cap_end and text[i] not in ";\n":
        i += 1
    raw = text[rhs_start:i].strip()
    raw = raw.rstrip(",").strip()
    return {_strip_quotes(raw)}


def _extract_list(text: str, rhs_start: int) -> "set[str] | None":
    """kind=list (default): skip whitespace to the first `[` or `{`; depth-
    count that bracket kind and split the inner region at top-level commas.
    `[...]` elements are kept as-is (quotes stripped). `{...}` (enum object)
    entries are split at their first top-level `:`; the KEY half is kept —
    see PCONST-04 for why keys were chosen over values. None if no `[`/`{`
    appears within `_LOOKAHEAD_CAP` chars, or the bracket never balances
    within `_MAX_SCAN` chars."""
    i = _skip_ws(text, rhs_start, _LOOKAHEAD_CAP)
    if i >= len(text) or text[i] not in "[{":
        return None
    open_ch = text[i]
    close_ch = "]" if open_ch == "[" else "}"
    span = _scan_balanced(text, open_ch, close_ch, i)
    if span is None:
        return None
    open_idx, close_idx = span
    inner = text[open_idx + 1 : close_idx]
    parts = [p for p in _split_top_level(inner) if p.strip()]
    values: set[str] = set()
    if open_ch == "[":
        for p in parts:
            values.add(_strip_quotes(p.strip()))
    else:
        for p in parts:
            key_raw = _split_key(p).strip()
            values.add(_strip_quotes(key_raw))
    return values


def extract_literal_set(file_text: str, locator: str, kind: str) -> "set[str] | None":
    """The novel core (PCONST-04): find `locator`'s declaration/key in
    `file_text` and extract its literal value(s) as a set of strings.
    Returns None if `locator` is not found at all — distinct from a found-
    but-empty set (an empty array literal is a legitimate, if suspicious,
    value; "not found" means the row can't even be graded)."""
    rhs_start = _find_identifier_assignment(file_text, locator)
    if rhs_start is None:
        return None
    if kind == "scalar":
        return _extract_scalar(file_text, rhs_start)
    return _extract_list(file_text, rhs_start)


def _format_set(vals: "set[str]") -> str:
    """Render a (possibly large) diff side capped to `_DIFF_CAP` items —
    PCONST-06: a 200-entry drift must not flood the terminal."""
    ordered = sorted(vals)
    shown = ordered[:_DIFF_CAP]
    more = len(ordered) - _DIFF_CAP
    suffix = f", …(+{more} more)" if more > 0 else ""
    return "{" + ", ".join(shown) + suffix + "}"


# --------------------------------------------------------------------------
# Per-table / per-row verdict (PCONST-03).
# --------------------------------------------------------------------------

def _analyze(text: str, contract_path: "Path | None") -> "tuple[list[str], str]":
    """Single linear pass shared by evaluate()/findings(). Returns
    (findings, summary): a non-empty findings list means fail."""
    if not text or not text.strip():
        return ["port-const file empty"], ""

    lines = tp.extract_scope(text, START, END).splitlines()
    tables = tp.iter_tables(lines, _resolve_header)

    if not tables:
        return [
            "no port-constant table found "
            "(cần bảng có cột Constant + Source + Built — check2 port-const diff)"
        ], ""

    fs: list[str] = []
    verified_total = 0

    for t_idx, table in enumerate(tables):
        label_col = table["label_col"]
        source_col = table["source_col"]
        built_col = table["built_col"]
        kind_col = table["kind_col"]
        table_label = tp.nearest_heading(lines, table["header_idx"]) or f"table {t_idx + 1}"

        row_idx = 0
        j = table["row_start"]
        while j < table["row_end"]:
            cells = _split_row(lines[j])
            if _is_separator_row(cells):
                j += 1
                continue
            row_idx += 1
            label = _row_label(cells, label_col, row_idx)

            source_cell = cells[source_col] if source_col < len(cells) else ""
            built_cell = cells[built_col] if built_col < len(cells) else ""
            kind_cell = cells[kind_col] if kind_col is not None and kind_col < len(cells) else ""
            kind = "scalar" if _norm(kind_cell).lower() == "scalar" else "list"

            src_loc = _parse_locator_cell(source_cell)
            if src_loc is None:
                fs.append(
                    f'constant {label}: malformed source locator '
                    f'(expected <filepath>#<identifier>): "{_norm(source_cell)}"'
                )
                j += 1
                continue
            built_loc = _parse_locator_cell(built_cell)
            if built_loc is None:
                fs.append(
                    f'constant {label}: malformed built locator '
                    f'(expected <filepath>#<identifier>): "{_norm(built_cell)}"'
                )
                j += 1
                continue

            src_path_str, src_ident = src_loc
            built_path_str, built_ident = built_loc

            src_text, src_err = _read_declared_file(src_path_str, contract_path)
            if src_err is not None:
                fs.append(f"constant {label}: source {src_err}")
                j += 1
                continue
            built_text, built_err = _read_declared_file(built_path_str, contract_path)
            if built_err is not None:
                fs.append(f"constant {label}: built {built_err}")
                j += 1
                continue

            src_set = extract_literal_set(src_text, src_ident, kind)
            if src_set is None:
                fs.append(f'constant {label}: locator "{src_ident}" not found in {src_path_str}')
                j += 1
                continue
            built_set = extract_literal_set(built_text, built_ident, kind)
            if built_set is None:
                fs.append(f'constant {label}: locator "{built_ident}" not found in {built_path_str}')
                j += 1
                continue

            if src_set != built_set:
                missing = src_set - built_set
                extra = built_set - src_set
                if missing and extra:
                    diff = f"is MISSING {_format_set(missing)} and has EXTRA {_format_set(extra)}"
                elif missing:
                    diff = f"is MISSING {_format_set(missing)}"
                else:
                    diff = f"has EXTRA {_format_set(extra)}"
                fs.append(
                    f"constant {label}: built {diff} "
                    f"(source {src_path_str}#{src_ident} vs built {built_path_str}#{built_ident})"
                )
                j += 1
                continue

            verified_total += 1
            j += 1

        if row_idx == 0:
            # A bare header with zero body rows is an ungraded claim, not a
            # pass — mirrors DBIND-02/GOLD-02's F7 fix.
            fs.append(f"{table_label} has a port-constant table header but no rows")

    summary = f"{verified_total} port-constant(s) verified across {len(tables)} table(s)"
    return fs, summary


def evaluate_map(text: str, path: "Path | None" = None) -> "tuple[bool, str]":
    """Core PCONST-02/03 verdict over a port-const document (fail-fast).
    Returns (ok, reason) — the FIRST problem, or a pass summary."""
    fs, summary = _analyze(text, path)
    if fs:
        return False, fs[0]
    return True, summary


def findings(text: str, path: "Path | None" = None) -> list[str]:
    """ALL failure reasons for a port-const document (empty list = pass):
    one finding per problematic row. `path` resolves relative locator
    paths — see PCONST-05."""
    return _analyze(text, path)[0]


# --------------------------------------------------------------------------
# Gate descriptor — consumed by the contract-gate CLI registry.
# --------------------------------------------------------------------------

KEY = "port-const"
TITLE = "Port-constant diff"
# PCONST-08: narrow, no bare-substring catch-all (GOLD-07 discipline).
GLOBS = ("*.portconst.md", "*.port-const.md")


def contains_port_const_table(text: str) -> bool:
    """True iff `text` has at least one qualifying port-const table (a
    header with a DISTINCT Source and a DISTINCT Built column). Lets the
    CLI skip files that merely share a generic name but hold a different
    kind of contract — a gate should not fail a file it does not own. Uses
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
    return contains_port_const_table(text)


def evaluate(text: str, path: "Path | None" = None) -> "tuple[bool, str]":
    # path resolves declared source/built files (PCONST-05) — unlike
    # data_binding/golden_record, this gate needs on-disk resolution.
    return evaluate_map(text, path)


DRAFT_GUIDANCE = """\
Draft a Port-constant diff table: for each constant/enum/dropdown-option
list/business-rule string that was PORTED from the legacy (source) repo
into the new (built) repo, pin BOTH sides' exact file + identifier so the
gate can diff the real literal VALUES — not just confirm a source exists.

For each row you MUST fill:
- Constant: a short human name (e.g. `種類 dropdown`, `chibanSortOrder`).
- Source: `<filepath>#<identifier>` in the LEGACY repo — the exact
  export/const/variable name holding the list or scalar.
- Built: `<filepath>#<identifier>` in the TARGET (ported) repo — same rule.
- Kind: `list` (an option array, or an enum object — default; leave blank)
  or `scalar` (a single business-rule string/number).

CRITICAL — do NOT game the gate: if you have not actually located the
identifier in one of the two repos, do NOT invent a plausible-looking
path/identifier — leave the cell `?` (a short reason after it is welcome,
e.g. `? not yet ported`). A fabricated locator that happens to parse
defeats the entire point of this gate — it exists BECAUSE a real port
silently dropped 10 北海道 region entries from a dropdown, and a guessed
locator would hide that exact bug class again.

Output ONLY the completed markdown contract below (keep the table shape);
no prose before or after."""


TEMPLATE = """\
# Port-constant diff — <constant/dropdown name>

> Pin each PORTED constant/literal (dropdown list, enum, business-rule
> string) side by side: where it lives in the SOURCE (legacy) repo vs the
> BUILT (target) repo. A locator cell is `<filepath>#<identifier>`, e.g.
> `apps/legacy/src/constants/prefecture.js#PREFECTURE_OPTIONS`. Absolute
> paths are the common case (source and built usually live in DIFFERENT
> repos). Kind is `list` (array/enum-object — default) or `scalar` (a
> single string/number constant).

<!-- port-const:start -->
| Constant | Source (legacy repo) | Built (target repo) | Kind |
|----------|------------------------|------------------------|------|
| <name> | <path/to/legacy/file.js#IDENTIFIER> | <path/to/react/file.tsx#IDENTIFIER> | list |
<!-- port-const:end -->
"""


def resolve_map_path(args: argparse.Namespace) -> Path:
    if args.map:
        return Path(args.map)
    return Path(args.repo) / ".port" / f"{args.task}.portconst.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="port_const_gate",
        description=(
            "Advisory port-constant diff (PCONST-01): verify every PORTED "
            "constant/literal's real value set is IDENTICAL between its "
            "source-repo declaration and its built-repo declaration."
        ),
    )
    p.add_argument("--map", help="Path to the port-const markdown file")
    p.add_argument("--repo", help="Target repo root (used together with --task)")
    p.add_argument("--task", help="Task slug (used together with --repo)")
    return p


def main(argv: "list[str] | None" = None) -> int:
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
        print("fail port-const file not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read port-const file: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate(text, path)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
