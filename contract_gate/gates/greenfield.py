#!/usr/bin/env python3
"""Greenfield oracle gate — pre-BUILD hard block for design+spec tasks (GREEN-01, plan 05-01).

This is the greenfield/design+spec equivalent of `manifest_gate.py`'s P1->P3
hard block. Where the port arm checks a Legacy Behavior Manifest, a
greenfield/design+spec task (build_kind in {handoff, design}, no legacy code
to diff against) has no manifest at all — its oracle is a **2-layer** one:
a Design-ref (what the mockup/design says) PLUS an Observable (a runnable
assertion against the real artifact). This gate makes "both layers present
before build starts" a runnable hard block instead of an advisory checklist
line, closing the gap that let the sales-activity-report PDF task ship with
nothing to assert against.

D-05 (stdlib-only, hard verdict — mirrors manifest_gate.py's D-01/D-03):
imports below are limited to argparse/sys/pathlib. NO third-party package,
NO .venv/pip install — this must run under a bare `python3` with zero setup.
On success prints `pass <summary>` to stdout and exits 0. On any failure
prints `fail <one-line reason>` to stderr and exits 1 — the exit code +
`pass`/`fail` prefix are the load-bearing contract the SKILL.md wiring
(05-03) and the exam run (05-04) depend on. The micro-format of the reason
line is free.

D-02 (pass condition — the 2-layer oracle, row shape): a spec passes iff, in
order:
  1. the file exists and is non-empty after strip;
  2. its behavior table parses — a markdown pipe table whose header row has
     BOTH a column recognizable as "Design-ref" AND a column recognizable as
     "Observable";
  3. every behavior/body row in that table has a non-empty Observable cell
     (mandatory ALWAYS, even for visual-exempt specs — see D-04 below);
  4. unless the spec (or the row) is visual-exempt, every row also has a
     non-empty AND resolvable Design-ref cell (see D-03).
Whitespace-only or a lone "-"/"—"/"–"/"ー"/"−" counts as an empty cell. The
failure reason names the offending row.

D-03 (Design-ref resolvability, NO NETWORK): a Design-ref cell is either (a)
a Claude Design link containing `/design/h/` — format-checked non-empty
ONLY, this gate never opens a socket or curls it, preserving the
stdlib-only/no-network discipline verbatim from manifest_gate.py's D-01 — or
(b) a local mockup path (HTML/PDF/image), which is resolved relative to the
spec file's directory and must `Path.exists()`. Both forms are accepted
because real greenfield tasks have used both a Claude Design bundle link and
a plain local HTML mockup under `~/Downloads`.

D-04 (no-visual exempt, explicit only): a pure logic/artifact spec with no
mockup may exempt the Design-ref layer, but ONLY via an explicit flag — a
`visual: none` line in the spec (front-matter or header) exempts every row
in the file, or a per-row sentinel Design-ref value of `N/A-logic` exempts
that single row. A blank Design-ref cell is NEVER treated as exempt — the
exempt flag must be tường minh (explicit), never inferred from omission.
Observable stays mandatory non-empty regardless of exemption.

D-06 (Confidence + Restated columns, OPT-IN, cognitive-forcing-function):
the sales-activity-report retro showed this gate catches "AI had no
source" (a blank cell) but not "a human rubber-stamped a cell they never
actually verified" — the more expensive failure mode, since the row
*looks* sourced and ships wrong anyway. If the header carries a Confidence
column (needle "confidence"/"conf"), the gate additionally requires: (1) a
Restated/Human column (needle "restated"/"human"/"diễn giải") must also
exist — a Confidence column with nowhere to put the human's own words is a
schema error; (2) every row's Confidence cell is non-empty (convention,
not enforced glyph-by-glyph: 🟢 sourced/certain, 🟡 inferred, 🔴
unresolved); (3) any row NOT marked 🟢 must carry a non-empty Restated
cell that is NOT a verbatim copy of that row's Design-ref or Observable
cell (case-insensitive compare) — forcing the human to state the row's
meaning in their own words before it counts as reviewed, instead of
silence/copy-paste passing as agreement. Both columns are OPTIONAL: a spec
with no Confidence column is graded exactly as before (D-02..D-04 only),
so no existing spec regresses — this only activates once an author opts in
by adding the column, which the updated DRAFT_GUIDANCE does automatically
for freshly drafted specs.

D-07 (multi-table files — loop, don't stop at the first): a single spec
file may hold MORE THAN ONE behavior table — e.g. one master spec covering
N screens, one table per `## Màn <k>` section. Before this fix the gate
located only the FIRST table with Design-ref+Observable columns, graded
its rows, and silently stopped: any violation in a later table (missing
Observable, D-06 empty Restated, anything) was never seen and the file
still reported `pass`. Demonstrated live (2026-07-09): a 3-table demo spec
with real D-06 violations in tables 2 and 3 reported "pass 2 behavior
row(s) verified" — counting only table 1's rows, a false PASS (the worst
failure mode a gate can have). Fixed: `_iter_tables()` scans the WHOLE
file and returns every table it finds, in order; each keeps its OWN
resolved column indices (tables need not share a layout) and its own
[row_start, row_end) line range. Every table is graded — evaluate_spec
still fails fast (stops at the first violation, across tables in file
order); findings() collects violations from ALL tables for `check --all`.
A table's failure reason is prefixed with a label: the nearest preceding
markdown heading line (e.g. "Màn 2: report-2 (物件確認)"), or `table N`
(1-based discovery order) when no heading precedes it — so a 10-screen
master spec's failure names the screen, not just a bare row number.

D-01 (format-forgiving parser, mirrors manifest_gate.py's D-05): the
Design-ref column is located by a case-insensitive substring match against
the header cell ("design", "mockup", or "design-ref"); the Observable column
by ("observable" or "assert"). Column position/order and exact column count
do not matter (column-reorder tolerant). Leading/trailing whitespace and
cosmetic formatting inside cells are accepted as-is — this gate's ONLY job
is to catch a missing oracle layer, not to lint markdown.

T-02-01 (DoS mitigation, inherited from manifest_gate.py): the parser is a
linear, line-by-line scan using only str.split("|") — no regex, hence no
catastrophic-backtracking surface. A >=5000-row / pathological input
completes in well under 1s.

Usage:
    python3 greenfield_gate.py --spec <path/to/.greenfield/task.spec.md>
    python3 greenfield_gate.py --repo <target-repo> --task <task>
        (resolves to <target-repo>/.greenfield/<task>.spec.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Whitespace-only (after strip -> "") or a lone dash/prolonged-sound-mark/minus
# counts as an empty cell (D-02.3). Superset of common dash look-alikes.
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−"}

# A Design-ref that "looks like" a local mockup path -- either it contains a
# path separator, or it ends in a recognized mockup file extension.
_LOCAL_DESIGNREF_EXTENSIONS = (".html", ".pdf", ".png", ".jpg", ".jpeg")

# D-06 opt-in columns: needles for header detection + the "certain" marker.
CONFIDENCE_NEEDLES = ("confidence", "conf")
RESTATED_NEEDLES = ("restated", "human", "diễn giải", "dien giai")
_GREEN_MARKER = "🟢"

# D-01/D-07 shared column-detection needles (one source, used by _iter_tables
# AND applies() so the two never drift out of sync).
DESIGN_NEEDLES = ("design", "mockup", "design-ref")
OBSERVABLE_NEEDLES = ("observable", "assert")
BEHAVIOR_NEEDLES = ("behavior", "hành vi", "hanh vi")


def _norm(cell: str) -> str:
    return cell.strip()


def _is_empty_cell(cell: str) -> bool:
    return _norm(cell) in EMPTY_CELL_MARKERS


def _is_green_confidence(cell: str) -> bool:
    """D-06: a Confidence cell counts as 🟢 (sourced/certain, no Restated
    needed) if it carries the green-circle glyph, or the plain words
    "green"/"ok" for authors who can't type the emoji. Anything else
    non-empty (🟡, 🔴, prose) is treated as NOT green -> needs Restated."""
    c = _norm(cell)
    if not c:
        return False
    return _GREEN_MARKER in c or c.lower() in ("green", "ok")


def _looks_like_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _split_row(line: str) -> list[str]:
    """Split a markdown pipe-table row into raw cells (format-forgiving:
    leading/trailing pipe optional, no whitespace/column-count validation)."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
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


def _find_col(header_cells: list[str], needles: tuple[str, ...]) -> int | None:
    for i, cell in enumerate(header_cells):
        low = cell.lower()
        if any(needle in low for needle in needles):
            return i
    return None


def _spec_is_visual_exempt(text: str) -> bool:
    """D-04 file-level exempt flag: a line declaring `visual: none` (in
    front-matter or elsewhere) exempts the Design-ref layer for every row of
    this spec. Observable stays mandatory regardless."""
    for line in text.splitlines():
        s = line.strip().lower()
        if s.startswith("visual:") and "none" in s:
            return True
    return False


def _nearest_heading(lines: list[str], idx: int) -> str | None:
    """D-07: label a table by the nearest preceding markdown heading
    (`#`.."######" + text) above line `idx`, stripped of the leading `#`s
    -- gives readable per-table failure reasons in a multi-table master
    spec (e.g. "Màn 2: report-2 (物件確認)"). None if nothing precedes it."""
    i = idx - 1
    while i >= 0:
        s = lines[i].strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        i -= 1
    return None


def _iter_tables(lines: list[str]) -> list[dict]:
    """D-07: locate EVERY behavior table in the file, not just the first.
    Each descriptor carries its own resolved column indices (tables need
    not share a layout) plus the [row_start, row_end) line range of its
    body rows. Linear single pass (T-02-01 preserved): once a table's body
    is found, the scan jumps straight past it instead of rescanning."""
    n = len(lines)
    tables: list[dict] = []
    i = 0
    while i < n:
        line = lines[i]
        if _looks_like_table_row(line):
            cells = _split_row(line)
            if not _is_separator_row(cells):
                d_col = _find_col(cells, DESIGN_NEEDLES)
                o_col = _find_col(cells, OBSERVABLE_NEEDLES)
                if d_col is not None and o_col is not None:
                    header_idx = i
                    header_cells = cells
                    j = header_idx + 1
                    if j < n and _looks_like_table_row(lines[j]) and _is_separator_row(_split_row(lines[j])):
                        j += 1
                    row_start = j
                    while j < n and _looks_like_table_row(lines[j]):
                        j += 1
                    tables.append(
                        {
                            "label": _nearest_heading(lines, header_idx) or f"table {len(tables) + 1}",
                            "design_col": d_col,
                            "obs_col": o_col,
                            "behavior_col": _find_col(header_cells, BEHAVIOR_NEEDLES),
                            "confidence_col": _find_col(header_cells, CONFIDENCE_NEEDLES),
                            "restated_col": _find_col(header_cells, RESTATED_NEEDLES),
                            "row_start": row_start,
                            "row_end": j,
                        }
                    )
                    i = j
                    continue
        i += 1
    return tables


def _check_row(cells: list[str], table: dict, spec_dir: Path, file_exempt: bool) -> str | None:
    """First violation reason for one row against its OWN table's column
    layout, or None if the row passes. Precedence mirrors the pre-D-07
    behavior exactly: Observable, then Design-ref, then D-06 Confidence/
    Restated -- a row failing an earlier check is never also reported for
    a later one."""
    design_col = table["design_col"]
    obs_col = table["obs_col"]

    observable_cell = cells[obs_col] if obs_col < len(cells) else ""
    if _is_empty_cell(observable_cell):
        return "has empty Observable"

    design_cell = cells[design_col] if design_col < len(cells) else ""
    row_exempt = file_exempt or _norm(design_cell) == "N/A-logic"
    if not row_exempt:
        if _is_empty_cell(design_cell):
            return "has empty Design-ref"
        if not _designref_ok(design_cell, spec_dir):
            return "has unresolvable Design-ref"

    confidence_col = table["confidence_col"]
    if confidence_col is not None:
        confidence_cell = cells[confidence_col] if confidence_col < len(cells) else ""
        if _is_empty_cell(confidence_cell):
            return "has empty Confidence"
        if not _is_green_confidence(confidence_cell):
            restated_col = table["restated_col"]
            restated_cell = cells[restated_col] if restated_col < len(cells) else ""
            if _is_empty_cell(restated_cell):
                return "is not 🟢-confidence but has empty Restated"
            restated_norm = _norm(restated_cell).lower()
            if restated_norm in (_norm(design_cell).lower(), _norm(observable_cell).lower()):
                return "Restated is a copy of Design-ref/Observable, not the human's own words"

    return None


def _designref_ok(cell: str, spec_dir: Path) -> bool:
    """D-03 resolvability, NO NETWORK. A `/design/h/<code>` Claude Design
    link is format-checked non-empty ONLY — never curled. A local mockup
    path (contains a path separator, or ends in a recognized mockup
    extension) is resolved relative to spec_dir and must exist on disk."""
    c = _norm(cell)
    if not c:
        return False
    if "/design/h/" in c:
        return True
    looks_local = "/" in c or c.lower().endswith(_LOCAL_DESIGNREF_EXTENSIONS)
    if not looks_local:
        return False
    p = Path(c)
    if not p.is_absolute():
        p = spec_dir / p
    return p.exists()


def evaluate_spec(text: str, spec_dir: Path | None = None) -> tuple[bool, str]:
    """Core D-02 verdict over greenfield spec text. Returns (ok, reason).

    Forked from manifest_gate.py's evaluate_manifest, but locates and checks
    TWO columns per row (Design-ref AND Observable) instead of one, and
    honors the D-04 visual-exempt flag. Grades EVERY behavior table in the
    file (D-07), not just the first — fails fast at the first violation
    found in file order, across tables. `reason` is a short one-line
    summary: on success a pass summary, on failure the block reason naming
    the offending table + row. Linear parse (T-02-01) — no regex, single
    pass over lines. `spec_dir` anchors relative local Design-ref paths
    (defaults to the current working directory when not given, e.g. in
    unit tests).
    """
    if not text or not text.strip():
        return False, "spec empty"

    if spec_dir is None:
        spec_dir = Path(".")

    file_exempt = _spec_is_visual_exempt(text)
    lines = text.splitlines()
    tables = _iter_tables(lines)

    if not tables:
        return (
            False,
            "no behavior table with resolvable Design-ref and Observable columns found",
        )

    total_rows = 0
    for table in tables:
        if table["confidence_col"] is not None and table["restated_col"] is None:
            return (
                False,
                f'{table["label"]}: Confidence column present but no Restated/Human column found (D-06)',
            )

        behavior_col = table["behavior_col"]
        table_row_count = 0
        j = table["row_start"]
        while j < table["row_end"]:
            cells = _split_row(lines[j])
            if _is_separator_row(cells):
                j += 1
                continue
            table_row_count += 1
            total_rows += 1

            if behavior_col is not None and behavior_col < len(cells):
                label = cells[behavior_col]
            else:
                label = cells[0] if cells else "?"

            reason = _check_row(cells, table, spec_dir, file_exempt)
            if reason is not None:
                return False, f'{table["label"]} row {table_row_count} ("{label}") {reason}'

            j += 1

    if total_rows == 0:
        return False, "spec has no rows"

    if len(tables) == 1:
        return True, f"{total_rows} behavior row(s) verified"
    return True, f"{total_rows} behavior row(s) verified across {len(tables)} table(s)"


# --------------------------------------------------------------------------
# Gate descriptor — consumed by the contract-gate CLI registry.
# --------------------------------------------------------------------------

KEY = "greenfield"
TITLE = "Greenfield 2-layer oracle spec"
GLOBS = ("*.spec.md", "*.greenfield.md")


def _has_col(header_cells: list[str], needles: tuple[str, ...]) -> bool:
    return _find_col(header_cells, needles) is not None


def applies(text: str) -> bool:
    """True iff some table header carries BOTH a Design-ref and an Observable
    column — the signature of a greenfield 2-layer oracle spec. This guards the
    gate against judging a manifest or a data-binding map with a shared name."""
    for line in text.splitlines():
        if not _looks_like_table_row(line):
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        if _has_col(cells, DESIGN_NEEDLES) and _has_col(cells, OBSERVABLE_NEEDLES):
            return True
    return False


def evaluate(text: str, path: Path | None = None) -> tuple[bool, str]:
    spec_dir = path.parent if path is not None else Path(".")
    return evaluate_spec(text, spec_dir)


def findings(text: str, path: Path | None = None) -> list[str]:
    """ALL failure reasons (empty = pass) across EVERY behavior table in the
    file (D-07) — one finding per violating row, prefixed with that row's
    table label. Mirrors evaluate_spec's per-row precedence (Observable,
    then Design-ref, then D-06). Backs `check --all`."""
    spec_dir = path.parent if path is not None else Path(".")
    if not text or not text.strip():
        return ["spec empty"]
    file_exempt = _spec_is_visual_exempt(text)
    lines = text.splitlines()
    tables = _iter_tables(lines)
    if not tables:
        return ["no behavior table with resolvable Design-ref and Observable columns found"]

    out: list[str] = []
    total_rows = 0
    for table in tables:
        if table["confidence_col"] is not None and table["restated_col"] is None:
            out.append(f'{table["label"]}: Confidence column present but no Restated/Human column found (D-06)')
            continue

        behavior_col = table["behavior_col"]
        table_row_count = 0
        j = table["row_start"]
        while j < table["row_end"]:
            cells = _split_row(lines[j])
            if _is_separator_row(cells):
                j += 1
                continue
            table_row_count += 1
            total_rows += 1

            if behavior_col is not None and behavior_col < len(cells):
                label = cells[behavior_col]
            else:
                label = cells[0] if cells else "?"

            reason = _check_row(cells, table, spec_dir, file_exempt)
            if reason is not None:
                out.append(f'{table["label"]} row {table_row_count} ("{label}") {reason}')

            j += 1

    if total_rows == 0:
        return ["spec has no rows"]
    return out


DRAFT_GUIDANCE = """\
Draft a greenfield 2-layer oracle spec: every behavior row needs BOTH a
Design-ref (what the mockup/design says) AND an Observable (a runnable
assertion against the real artifact — a DOM check, a network call, a DB row).

- Design-ref: a Claude Design link (contains `/design/h/`) OR a local mockup
  path (HTML/PDF/image) that exists on disk. If a row is pure logic with no
  visual, put `N/A-logic` in Design-ref (only when truly visual-exempt).
- Observable: ALWAYS required — never leave it blank. Phrase it so it can be
  checked automatically ("cell #price shows ¥29,880" beats "price looks right").
- Confidence + Restated (D-06, always include both columns): mark each row
  🟢 (you read it straight off the source, no inference) or 🟡/🔴 (you
  inferred it, or found nothing). For every row NOT marked 🟢, leave the
  Restated cell for the HUMAN reviewer to fill in their own words — do
  NOT pre-fill it yourself; a human paraphrase that differs from your
  Design-ref/Observable text is the whole point (it proves they actually
  re-derived the row instead of rubber-stamping your draft).

CRITICAL — do NOT game the gate: if you cannot name a real Observable, that is
a blind spot to resolve, not a cell to pad. Never mark a row 🟢 unless you
can point to the exact source line/screenshot — when unsure, mark 🟡/🔴 so
the human is forced to weigh in, rather than inflating confidence to skip
review. Output ONLY the completed markdown spec below.

Master spec covering multiple screens (D-07): you do NOT need one file per
screen. Repeat the table once per screen/section, each under its own
markdown heading (e.g. `## Màn 2: report-2 (物件確認)`) — every table is
graded independently and a failure names the heading it's under, so a
10-screen master spec still gets full per-screen coverage in one file."""


TEMPLATE = """\
# Greenfield spec — <task>

<!-- visual: none  (uncomment ONLY for a pure-logic spec with no mockup) -->

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|------------|------------|------------|----------|
| 1 | <what the screen does> | <design link or ./mockup.html> | <runnable assertion> | 🟢 | |
| 2 | <pure-logic behavior>  | N/A-logic | <assertion> | 🟡 | <human: what you think this really means, in your own words> |
"""


def resolve_spec_path(args: argparse.Namespace) -> Path:
    if args.spec:
        return Path(args.spec)
    return Path(args.repo) / ".greenfield" / f"{args.task}.spec.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="greenfield_gate",
        description=(
            "Pre-BUILD hard block for greenfield/design+spec tasks: verify "
            "the 2-layer oracle spec is persisted, non-empty, and every "
            "behavior row has a non-empty Observable cell plus a non-empty "
            "AND resolvable Design-ref cell (unless visual-exempt) (D-02)."
        ),
    )
    p.add_argument("--spec", help="Path to the .greenfield/<task>.spec.md file")
    p.add_argument("--repo", help="Target repo root (used together with --task)")
    p.add_argument("--task", help="Task slug (used together with --repo)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    has_spec = bool(args.spec)
    has_repo_task = bool(args.repo) and bool(args.task)
    has_partial_repo_task = bool(args.repo) != bool(args.task)

    if has_spec and (args.repo or args.task):
        print("fail specify --spec OR --repo+--task, not both", file=sys.stderr)
        return 1
    if has_partial_repo_task:
        print("fail --repo and --task must be given together", file=sys.stderr)
        return 1
    if not has_spec and not has_repo_task:
        print(
            "fail either --spec or both --repo and --task are required",
            file=sys.stderr,
        )
        return 1

    path = resolve_spec_path(args)
    if not path.exists() or path.is_dir():
        print("fail spec not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read spec: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate_spec(text, path.parent)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
