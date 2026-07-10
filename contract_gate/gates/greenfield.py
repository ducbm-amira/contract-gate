#!/usr/bin/env python3
"""Greenfield oracle gate — pre-BUILD hard block for design+spec tasks (GREEN-01, plan 05-01).

This is the greenfield/design+spec equivalent of `manifest.py`'s P1->P3
hard block. Where the port arm checks a Legacy Behavior Manifest, a
greenfield/design+spec task (build_kind in {handoff, design}, no legacy code
to diff against) has no manifest at all — its oracle is a **2-layer** one:
a Design-ref (what the mockup/design says) PLUS an Observable (a runnable
assertion against the real artifact). This gate makes "both layers present
before build starts" a runnable hard block instead of an advisory checklist
line, closing the gap that let the sales-activity-report PDF task ship with
nothing to assert against.

D-05 (stdlib-only, hard verdict — mirrors manifest.py's D-01/D-03):
imports below are limited to argparse/sys/pathlib plus the sibling
`contract_gate.tableparse` module (also stdlib-only). NO third-party
package, NO .venv/pip install — this must run under a bare `python3` with
zero setup. On success prints `pass <summary>` to stdout and exits 0. On
any failure prints `fail <one-line reason>` to stderr and exits 1 — the
exit code + `pass`/`fail` prefix are the load-bearing contract the SKILL.md
wiring (05-03) and the exam run (05-04) depend on. The micro-format of the
reason line is free.

D-02 (pass condition — the 2-layer oracle, row shape): a spec passes iff, in
order:
  1. the file exists and is non-empty after strip;
  2. its behavior table parses — a markdown pipe table whose header row has
     BOTH a column recognizable as "Design-ref" AND a column recognizable as
     "Observable" (two DISTINCT columns — see the collision guard below);
  3. every behavior/body row in that table has a non-empty Observable cell
     (mandatory ALWAYS, even for visual-exempt specs — see D-04 below);
  4. unless the spec (or the row) is visual-exempt, every row also has a
     non-empty AND resolvable Design-ref cell (see D-03);
  5. every qualifying table has at least one body row (a header-only table
     is an ungraded claim, not a pass).
"Unfilled" is the family-wide `tableparse.is_empty_cell` rule: whitespace/
dash look-alikes AND placeholder tokens (?/TODO/TBD/WIP/…, leading `?`,
whole-cell `<scaffold>`). Before 2026-07-11 this gate only checked dash
look-alikes, so an Observable — or a D-06 Restated cell — of literally `?`
or `TODO` PASSED (a false PASS defeating D-06's whole purpose); fixed by
adopting the shared rule. The failure reason names the offending row.

Collision guard (ported from golden_record.py's GOLD-06, 2026-07-11): the
Design-ref and Observable columns are resolved as a mutually-exclusive pair
(Design-ref first, then Observable EXCLUDING it, via `tableparse.find_col`'s
`exclude` set). Before this, a single header cell containing both needle
sets — e.g. "Design & Observable assertion" — resolved BOTH columns to the
same index, silently collapsing the 2-layer oracle into 1 layer (one filled
cell satisfied both layers: a false PASS). Now such a table simply does not
qualify, which is the loud outcome.

D-03 (Design-ref resolvability, NO NETWORK): a Design-ref cell is either (a)
a Claude Design link containing `/design/h/`, or any `http(s)://` URL
(Figma, hosted mockup, …) — format-checked non-empty ONLY, this gate never
opens a socket or curls it, preserving the stdlib-only/no-network
discipline verbatim from manifest.py's D-01 — or (b) a local mockup path
(HTML/PDF/image), which is resolved relative to the spec file's directory
and must `Path.exists()`. All forms are accepted because real greenfield
tasks have used a Claude Design bundle link, a Figma URL, and a plain local
HTML mockup under `~/Downloads`.

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
N screens, one table per `## Màn <k>` section. All tables are graded, each
with its OWN resolved column indices; parsing is delegated to
`tableparse.iter_tables`, which ALSO handles tables abutting each other
with no blank line in between (the residue of the original D-07 bug — an
abutting table's rows used to be graded under the previous table's column
indices). A table's failure reason is prefixed with a label: the nearest
preceding markdown heading line (e.g. "Màn 2: report-2 (物件確認)"), or
`table N` (1-based discovery order) when no heading precedes it — so a
10-screen master spec's failure names the screen, not just a bare row
number.

D-01 (format-forgiving parser, mirrors manifest.py's D-05): the
Design-ref column is located by a case-insensitive substring match against
the header cell ("design", "mockup", or "design-ref"); the Observable column
by ("observable" or "assert"). Column position/order and exact column count
do not matter (column-reorder tolerant). Leading/trailing whitespace and
cosmetic formatting inside cells are accepted as-is — this gate's ONLY job
is to catch a missing oracle layer, not to lint markdown.

T-02-01 (DoS mitigation, inherited from manifest.py): the parser is a
linear, line-by-line scan using only split-based cell parsing — no regex,
hence no catastrophic-backtracking surface. A >=5000-row / pathological
input completes in well under 1s.

Usage:
    python3 -m contract_gate.gates.greenfield --spec <path/to/.greenfield/task.spec.md>
    python3 -m contract_gate.gates.greenfield --repo <target-repo> --task <task>
        (resolves to <target-repo>/.greenfield/<task>.spec.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .. import tableparse as tp
except ImportError:  # standalone `python3 contract_gate/gates/greenfield.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from contract_gate import tableparse as tp

# Shared family-wide helpers (see tableparse.py). Local aliases keep the
# historical names used throughout this module.
EMPTY_CELL_MARKERS = tp.EMPTY_CELL_MARKERS
_norm = tp.norm
_is_empty_cell = tp.is_empty_cell
_looks_like_table_row = tp.looks_like_table_row
_split_row = tp.split_row
_is_separator_row = tp.is_separator_row
_find_col = tp.find_col
_nearest_heading = tp.nearest_heading

# A Design-ref that "looks like" a local mockup path -- either it contains a
# path separator, or it ends in a recognized mockup file extension.
_LOCAL_DESIGNREF_EXTENSIONS = (".html", ".pdf", ".png", ".jpg", ".jpeg")

# D-06 opt-in columns: needles for header detection + the "certain" marker.
CONFIDENCE_NEEDLES = ("confidence", "conf")
RESTATED_NEEDLES = ("restated", "human", "diễn giải", "dien giai")
_GREEN_MARKER = "🟢"

# D-01/D-07 shared column-detection needles (one source, used by the header
# resolver AND applies() so the two never drift out of sync).
DESIGN_NEEDLES = ("design", "mockup", "design-ref")
OBSERVABLE_NEEDLES = ("observable", "assert")
BEHAVIOR_NEEDLES = ("behavior", "hành vi", "hanh vi")


def _is_green_confidence(cell: str) -> bool:
    """D-06: a Confidence cell counts as 🟢 (sourced/certain, no Restated
    needed) if it carries the green-circle glyph, or the plain words
    "green"/"ok" for authors who can't type the emoji. Anything else
    non-empty (🟡, 🔴, prose) is treated as NOT green -> needs Restated."""
    c = _norm(cell)
    if not c:
        return False
    return _GREEN_MARKER in c or c.lower() in ("green", "ok")


def _spec_is_visual_exempt(text: str) -> bool:
    """D-04 file-level exempt flag: a line declaring `visual: none` (in
    front-matter or elsewhere) exempts the Design-ref layer for every row of
    this spec. Observable stays mandatory regardless."""
    for line in text.splitlines():
        s = line.strip().lower()
        if s.startswith("visual:") and "none" in s:
            return True
    return False


def _resolve_header(cells: list[str]) -> dict | None:
    """A greenfield table qualifies iff its header has BOTH a Design-ref and
    a DISTINCT Observable column. Columns are resolved in priority order,
    each excluding indices already claimed (the GOLD-06 collision guard) —
    no two fields can silently resolve to the same column."""
    d_col = _find_col(cells, DESIGN_NEEDLES)
    if d_col is None:
        return None
    claimed = frozenset({d_col})
    o_col = _find_col(cells, OBSERVABLE_NEEDLES, exclude=claimed)
    if o_col is None:
        return None
    claimed = claimed | {o_col}
    confidence_col = _find_col(cells, CONFIDENCE_NEEDLES, exclude=claimed)
    if confidence_col is not None:
        claimed = claimed | {confidence_col}
    restated_col = _find_col(cells, RESTATED_NEEDLES, exclude=claimed)
    if restated_col is not None:
        claimed = claimed | {restated_col}
    return {
        "design_col": d_col,
        "obs_col": o_col,
        "behavior_col": _find_col(cells, BEHAVIOR_NEEDLES, exclude=claimed),
        "confidence_col": confidence_col,
        "restated_col": restated_col,
    }


def _iter_tables(lines: list[str]) -> list[dict]:
    """D-07: every behavior table in the file (abutting-table safe), each
    labeled by its nearest preceding heading."""
    tables = tp.iter_tables(lines, _resolve_header)
    for k, table in enumerate(tables):
        table["label"] = _nearest_heading(lines, table["header_idx"]) or f"table {k + 1}"
    return tables


def _check_row(cells: list[str], table: dict, spec_dir: Path, file_exempt: bool) -> str | None:
    """First violation reason for one row against its OWN table's column
    layout, or None if the row passes. Precedence: Observable, then
    Design-ref, then D-06 Confidence/Restated -- a row failing an earlier
    check is never also reported for a later one."""
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
    link OR any http(s):// URL (Figma, hosted mockup, …) is format-checked
    non-empty ONLY — never curled (before 2026-07-11 a Figma URL was
    misread as a local path, never existed on disk, and every row false-
    FAILED with 'unresolvable Design-ref'). A local mockup path (contains a
    path separator, or ends in a recognized mockup extension) is resolved
    relative to spec_dir and must exist on disk."""
    c = _norm(cell)
    if not c:
        return False
    if "/design/h/" in c:
        return True
    low = c.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return True
    looks_local = "/" in c or low.endswith(_LOCAL_DESIGNREF_EXTENSIONS)
    if not looks_local:
        return False
    p = Path(c)
    if not p.is_absolute():
        p = spec_dir / p
    return p.exists()


def _analyze(text: str, spec_dir: Path) -> tuple[list[str], str]:
    """Single linear pass backing evaluate_spec (fail-fast via first finding)
    and findings (collect-all). Returns (findings, summary)."""
    if not text or not text.strip():
        return ["spec empty"], ""

    file_exempt = _spec_is_visual_exempt(text)
    lines = text.splitlines()
    tables = _iter_tables(lines)

    if not tables:
        return [
            "no behavior table with resolvable Design-ref and Observable columns found"
        ], ""

    out: list[str] = []
    total_rows = 0
    for table in tables:
        if table["confidence_col"] is not None and table["restated_col"] is None:
            out.append(
                f'{table["label"]}: Confidence column present but no Restated/Human column found (D-06)'
            )
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
        if table_row_count == 0:
            # D-02.5: a header-only table is an ungraded claim, not a pass.
            out.append(f'{table["label"]} has a behavior table header but no rows')

    if total_rows == 0 and not out:
        return ["spec has no rows"], ""

    if len(tables) == 1:
        return out, f"{total_rows} behavior row(s) verified"
    return out, f"{total_rows} behavior row(s) verified across {len(tables)} table(s)"


def evaluate_spec(text: str, spec_dir: Path | None = None) -> tuple[bool, str]:
    """Core D-02 verdict over greenfield spec text. Returns (ok, reason).

    Grades EVERY behavior table in the file (D-07) — fails fast at the
    first violation found in file order, across tables. `reason` is a short
    one-line summary: on success a pass summary, on failure the block
    reason naming the offending table + row. `spec_dir` anchors relative
    local Design-ref paths (defaults to the current working directory when
    not given, e.g. in unit tests)."""
    fs, summary = _analyze(text, spec_dir if spec_dir is not None else Path("."))
    if fs:
        return False, fs[0]
    return True, summary


# --------------------------------------------------------------------------
# Gate descriptor — consumed by the contract-gate CLI registry.
# --------------------------------------------------------------------------

KEY = "greenfield"
TITLE = "Greenfield 2-layer oracle spec"
GLOBS = ("*.spec.md", "*.greenfield.md")


def applies(text: str) -> bool:
    """True iff some table header carries BOTH a Design-ref and a DISTINCT
    Observable column — the signature of a greenfield 2-layer oracle spec.
    Uses the SAME header resolver as grading, so applies()/evaluate() can
    never drift. This guards the gate against judging a manifest or a
    data-binding map with a shared name."""
    for line in text.splitlines():
        if not _looks_like_table_row(line):
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        if _resolve_header(cells) is not None:
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
    return _analyze(text, spec_dir)[0]


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
