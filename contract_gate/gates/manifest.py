#!/usr/bin/env python3
"""Port manifest gate — P1→P3 hard block (PORT-02, plan 02-01).

D-01 (stdlib-only): imports below are limited to argparse/sys/pathlib. NO
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
  3. every behavior/body row in that table has a non-empty Observable cell;
     whitespace-only or a lone "-"/"ー"/"−" counts as empty (D-04.3, names
     the offending row in the failure reason).

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
only str.split("|") — no regex, hence no catastrophic-backtracking surface.
A >=5000-row / pathological input completes in well under 1s.

Usage:
    python3 manifest_gate.py --manifest <path/to/route.manifest.md>
    python3 manifest_gate.py --repo <sdd-repo> --route <route>
        (resolves to <sdd-repo>/.port/<route>.manifest.md)
Exactly one of the two forms is required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Whitespace-only (after strip -> "") or a lone dash/prolonged-sound-mark/minus
# counts as an empty Observable cell (D-04.3). Superset of the three literal
# markers named in the plan ("-", "ー", "−") plus common dash look-alikes.
EMPTY_OBSERVABLE_MARKERS = {"", "-", "—", "–", "ー", "−"}


def _norm(cell: str) -> str:
    return cell.strip()


def _is_empty_observable(cell: str) -> bool:
    return _norm(cell) in EMPTY_OBSERVABLE_MARKERS


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


def evaluate_manifest(text: str) -> tuple[bool, str]:
    """Core D-04 verdict over manifest text. Returns (ok, reason).

    `reason` is a short one-line human-readable summary: on success a pass
    summary, on failure the block reason (D-03). Linear parse (T-02-01) —
    no regex, single pass over lines.
    """
    if not text or not text.strip():
        return False, "manifest empty"

    lines = text.splitlines()
    n = len(lines)

    header_idx: int | None = None
    header_cells: list[str] = []
    obs_col: int | None = None

    i = 0
    while i < n:
        line = lines[i]
        if _looks_like_table_row(line):
            cells = _split_row(line)
            if not _is_separator_row(cells):
                col = _find_col(cells, ("observable", "oracle"))
                if col is not None:
                    header_idx = i
                    header_cells = cells
                    obs_col = col
                    break
        i += 1

    if header_idx is None or obs_col is None:
        return False, "no behavior table with a resolvable Observable column found"

    behavior_col = _find_col(header_cells, ("hành vi", "behavior"))

    j = header_idx + 1
    if j < n and _looks_like_table_row(lines[j]) and _is_separator_row(_split_row(lines[j])):
        j += 1

    row_count = 0
    while j < n:
        line = lines[j]
        if not _looks_like_table_row(line):
            break
        cells = _split_row(line)
        if _is_separator_row(cells):
            j += 1
            continue
        row_count += 1
        observable_cell = cells[obs_col] if obs_col < len(cells) else ""
        if _is_empty_observable(observable_cell):
            if behavior_col is not None and behavior_col < len(cells):
                label = cells[behavior_col]
            else:
                label = cells[0] if cells else "?"
            return False, f'row {row_count} ("{label}") has empty Observable'
        j += 1

    if row_count == 0:
        return False, "behavior table has no rows"

    return True, f"{row_count} behavior row(s) verified"


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
        has_obs = _find_col(cells, ("observable", "oracle")) is not None
        has_design = _find_col(cells, ("design", "mockup", "design-ref")) is not None
        if has_obs and not has_design:
            return True
    return False


def evaluate(text: str, path: Path | None = None) -> tuple[bool, str]:
    # path unused — the manifest gate needs no on-disk resolution.
    return evaluate_manifest(text)


def findings(text: str, path: Path | None = None) -> list[str]:
    """ALL failure reasons (empty = pass): one finding per behavior row with an
    empty Observable. Mirrors evaluate_manifest. Backs `check --all`."""
    if not text or not text.strip():
        return ["manifest empty"]
    lines = text.splitlines()
    n = len(lines)

    header_idx = None
    header_cells: list[str] = []
    obs_col = None
    i = 0
    while i < n:
        if _looks_like_table_row(lines[i]):
            cells = _split_row(lines[i])
            if not _is_separator_row(cells):
                col = _find_col(cells, ("observable", "oracle"))
                if col is not None:
                    header_idx, header_cells, obs_col = i, cells, col
                    break
        i += 1
    if header_idx is None:
        return ["no behavior table with a resolvable Observable column found"]

    behavior_col = _find_col(header_cells, ("hành vi", "behavior"))
    j = header_idx + 1
    if j < n and _looks_like_table_row(lines[j]) and _is_separator_row(_split_row(lines[j])):
        j += 1

    out: list[str] = []
    row_count = 0
    while j < n:
        if not _looks_like_table_row(lines[j]):
            break
        cells = _split_row(lines[j])
        if _is_separator_row(cells):
            j += 1
            continue
        row_count += 1
        observable_cell = cells[obs_col] if obs_col < len(cells) else ""
        if _is_empty_observable(observable_cell):
            if behavior_col is not None and behavior_col < len(cells):
                label = cells[behavior_col]
            else:
                label = cells[0] if cells else "?"
            out.append(f'row {row_count} ("{label}") has empty Observable')
        j += 1

    if row_count == 0:
        return ["behavior table has no rows"]
    return out


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
Output ONLY the completed markdown manifest below."""


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
