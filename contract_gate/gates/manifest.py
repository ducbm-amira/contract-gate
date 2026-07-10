#!/usr/bin/env python3
"""Port manifest gate — P1→P3 hard block (PORT-02, plan 02-01).

D-01 (stdlib-only): imports below are limited to argparse/sys/pathlib plus
the sibling `contract_gate.tableparse` module (also stdlib-only). NO
third-party package, NO .venv/pip install — this must run under a bare
`python3` with zero setup. Do not add a third-party import here.

D-03 (hard verdict): on success prints `pass <summary>` to stdout and exits
0. On any failure prints `fail <one-line reason>` to stderr and exits 1 —
mirroring the TRACE_CLEAN/TRACE_GAP discipline used elsewhere in the suite
(skills/pinrich-cycle/SKILL.md "Gác cổng"). The micro-format of the line is
left to implementation discretion; the exit code + `pass`/`fail` prefix are
the load-bearing contract callers (sdd-port-page, pinrich-cycle) depend on.

D-04 (pass condition): a manifest passes iff, in order:
  1. the file exists and is non-empty after strip (D-04.1),
  2. its behavior table parses — a markdown pipe table whose header row has
     a column recognizable as "Observable" (D-04.2),
  3. every behavior/body row in that table has a non-empty, non-placeholder
     Observable cell (D-04.3, names the offending row in the failure
     reason). "Unfilled" is the family-wide `tableparse.is_empty_cell` rule:
     whitespace/dash look-alikes AND placeholder tokens (?/TODO/TBD/WIP/…,
     a leading `?`, a whole-cell `<scaffold>`). Before 2026-07-11 this gate
     only checked dash look-alikes, so an Observable of literally `TODO` or
     `?` PASSED — a false PASS, fixed by adopting the shared rule;
  4. every qualifying table has at least one body row — a header-only table
     ("I'll fill page 3 later") is an ungraded claim, not a pass.

D-05 (format-forgiving parser): the Observable column is located by a
case-insensitive substring match against the header cell — either the
literal word "observable" (EN variant, e.g. "Observable" / "Observable
(oracle...)") or the VN oracle phrasing containing "oracle" (e.g. "Observable
(oracle để verify)"). Column position/order and exact column count do not
matter (column-reorder tolerant). Leading/trailing whitespace, Vietnamese
prose, and full-width punctuation inside cells are accepted as-is — the
gate's ONLY job is to catch missing/empty Observable and unparseable/empty
manifests. It does NOT lint markdown, does NOT require an exact header
text/position, and does NOT reject cosmetic formatting.

D-06 (decision, deliberately NOT enforced here): this gate checks that
Observable is NON-EMPTY only. It does NOT verify that `invisible`-typed rows
carry a network/DB-shaped observable (e.g. "network POST .../x + 1 row DB")
— a stdlib text parser cannot reliably judge that shape and would
false-block on legitimate prose. That shape assertion is owned by the P4.5
characterization test (skills/sdd-port-page/SKILL.md, section "P4.5 —
Characterization test từ manifest"), not this gate. This comment is the
record that D-06 was decided, not silently dropped.

T-02-01 (DoS mitigation): the parser is a linear, line-by-line scan using
only split-based cell parsing — no regex, hence no catastrophic-backtracking
surface. A >=5000-row / pathological input completes in well under 1s.

D-07 (multi-table files — loop, don't stop at the first): a manifest file
may hold MORE THAN ONE behavior table. All tables are graded; parsing is
delegated to `tableparse.iter_tables`, which ALSO handles tables abutting
each other with no blank line in between (the residue of the original D-07
bug: the old scanner consumed an abutting table's header+rows as body rows
of the previous table and graded them under the wrong column indices — a
demonstrated false PASS, fixed 2026-07-11). A table's failure reason is
prefixed by the nearest preceding markdown heading (e.g. "Page 2: /detail"),
or `table N` (1-based discovery order) when no heading precedes it.

Usage:
    python3 -m contract_gate.gates.manifest --manifest <path/to/route.manifest.md>
    python3 -m contract_gate.gates.manifest --repo <sdd-repo> --route <route>
        (resolves to <sdd-repo>/.port/<route>.manifest.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .. import tableparse as tp
except ImportError:  # standalone `python3 contract_gate/gates/manifest.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from contract_gate import tableparse as tp

# Shared family-wide helpers (see tableparse.py). Local aliases keep the
# historical names used throughout this module.
EMPTY_OBSERVABLE_MARKERS = tp.EMPTY_CELL_MARKERS
_norm = tp.norm
_is_empty_observable = tp.is_empty_cell
_looks_like_table_row = tp.looks_like_table_row
_split_row = tp.split_row
_is_separator_row = tp.is_separator_row
_find_col = tp.find_col
_nearest_heading = tp.nearest_heading

OBSERVABLE_NEEDLES = ("observable", "oracle")
BEHAVIOR_NEEDLES = ("hành vi", "behavior")


def _resolve_header(cells: list[str]) -> dict | None:
    """A manifest table qualifies iff its header has an Observable column."""
    col = _find_col(cells, OBSERVABLE_NEEDLES)
    if col is None:
        return None
    return {
        "obs_col": col,
        "behavior_col": _find_col(cells, BEHAVIOR_NEEDLES, exclude=frozenset({col})),
    }


def _iter_tables(lines: list[str]) -> list[dict]:
    """D-07: every behavior table in the file (abutting-table safe), each
    labeled by its nearest preceding heading."""
    tables = tp.iter_tables(lines, _resolve_header)
    for k, table in enumerate(tables):
        table["label"] = _nearest_heading(lines, table["header_idx"]) or f"table {k + 1}"
    return tables


def _analyze(text: str) -> tuple[list[str], str]:
    """Single linear pass backing evaluate_manifest (fail-fast via first
    finding) and findings (collect-all). Returns (findings, summary)."""
    if not text or not text.strip():
        return ["manifest empty"], ""

    lines = text.splitlines()
    tables = _iter_tables(lines)

    if not tables:
        return ["no behavior table with a resolvable Observable column found"], ""

    out: list[str] = []
    total_rows = 0
    for table in tables:
        obs_col = table["obs_col"]
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
            observable_cell = cells[obs_col] if obs_col < len(cells) else ""
            if _is_empty_observable(observable_cell):
                if behavior_col is not None and behavior_col < len(cells):
                    label = cells[behavior_col]
                else:
                    label = cells[0] if cells else "?"
                out.append(f'{table["label"]} row {table_row_count} ("{label}") has empty Observable')
            j += 1
        if table_row_count == 0:
            # D-04.4: a header-only table is an ungraded claim, not a pass.
            out.append(f'{table["label"]} has a behavior table header but no rows')

    if total_rows == 0 and not out:
        return ["behavior table has no rows"], ""

    if len(tables) == 1:
        return out, f"{total_rows} behavior row(s) verified"
    return out, f"{total_rows} behavior row(s) verified across {len(tables)} table(s)"


def evaluate_manifest(text: str) -> tuple[bool, str]:
    """Core D-04 verdict over manifest text. Returns (ok, reason) — the
    FIRST violation in file order, or a pass summary."""
    fs, summary = _analyze(text)
    if fs:
        return False, fs[0]
    return True, summary


# --------------------------------------------------------------------------
# Gate descriptor — consumed by the contract-gate CLI registry.
# --------------------------------------------------------------------------

KEY = "manifest"
TITLE = "Legacy Behavior Manifest"
GLOBS = ("*.manifest.md",)


def applies(text: str) -> bool:
    """True iff some table header has an Observable column but NO Design-ref
    column — the signature of a port behavior manifest (a greenfield spec has
    both, and is owned by that gate; this defers to it)."""
    for line in text.splitlines():
        if not _looks_like_table_row(line):
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        has_obs = _find_col(cells, OBSERVABLE_NEEDLES) is not None
        has_design = _find_col(cells, ("design", "mockup", "design-ref")) is not None
        if has_obs and not has_design:
            return True
    return False


def evaluate(text: str, path: Path | None = None) -> tuple[bool, str]:
    # path unused — the manifest gate needs no on-disk resolution.
    return evaluate_manifest(text)


def findings(text: str, path: Path | None = None) -> list[str]:
    """ALL failure reasons (empty = pass) across EVERY behavior table in the
    file (D-07) — one finding per row with an empty Observable, prefixed
    with that row's table label. Mirrors evaluate_manifest. Backs
    `check --all`."""
    return _analyze(text)[0]


DRAFT_GUIDANCE = """\
Draft a Legacy Behavior Manifest: an inventory of EVERY behavior of the legacy
page you are porting — visible ones AND invisible side-effects (fire-and-forget
tracking, analytics beacons, DB writes, redirects). Each behavior row needs an
Observable: a concrete, checkable trace (a DOM assertion, a network call, a DB
row) that proves the ported code reproduced it.

Read the legacy source before drafting — grep for lifecycle hooks / event
handlers / API calls so invisible behaviors are not missed (they are the ones
ports drop). Every row MUST have a non-empty Observable.

CRITICAL — do NOT game the gate: an Observable you cannot state concretely is a
behavior you have not understood yet; go read the legacy, do not pad the cell.
Output ONLY the completed markdown manifest below.

Master manifest covering multiple pages/components (D-07): you do NOT need
one file per page. Repeat the table once per page/component, each under its
own markdown heading (e.g. `## Page 2: /detail`) — every table is graded
independently and a failure names the heading it's under."""


TEMPLATE = """\
# Legacy Behavior Manifest — <route>

| # | Behavior | Type | Observable (oracle to verify) |
|---|----------|------|-------------------------------|
| 1 | <visible behavior> | visible | <DOM/UI assertion> |
| 2 | <fire-and-forget side effect> | invisible | <network POST … / 1 row in table X> |
"""


def resolve_manifest_path(args: argparse.Namespace) -> Path:
    if args.manifest:
        return Path(args.manifest)
    return Path(args.repo) / ".port" / f"{args.route}.manifest.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manifest_gate",
        description=(
            "P1->P3 hard block: verify the Legacy Behavior Manifest is "
            "persisted, non-empty, and every behavior row has a non-empty "
            "Observable cell (D-04)."
        ),
    )
    p.add_argument("--manifest", help="Path to the manifest .md file")
    p.add_argument("--repo", help="SDD repo root (used together with --route)")
    p.add_argument("--route", help="Route slug (used together with --repo)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    has_manifest = bool(args.manifest)
    has_repo_route = bool(args.repo) and bool(args.route)
    has_partial_repo_route = bool(args.repo) != bool(args.route)

    if has_manifest and (args.repo or args.route):
        print("fail specify --manifest OR --repo+--route, not both", file=sys.stderr)
        return 1
    if has_partial_repo_route:
        print("fail --repo and --route must be given together", file=sys.stderr)
        return 1
    if not has_manifest and not has_repo_route:
        print(
            "fail either --manifest or both --repo and --route are required",
            file=sys.stderr,
        )
        return 1

    path = resolve_manifest_path(args)
    if not path.exists() or path.is_dir():
        print("fail manifest not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read manifest: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate_manifest(text)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
