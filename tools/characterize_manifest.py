#!/usr/bin/env python3
"""Manifest characterization adapter — the EVID-02 value/text oracle-assert
primitive for the PORT arm (D-07, plan 06-01).

Where `characterize_pdf.py` asserts a GREENFIELD spec's `target: pdf` rows
against a generated PDF's extracted text, this adapter asserts the PORT arm's
field-level Behavior Manifest Observable column against a captured artifact's
text — for the map/list exam this is the intercepted `by_lat_lng` marker-data
JSON, but the assert logic is identical, only the text source changes (fed
via `--text-file`, no PDF/pdftotext involved here).

"Present AND correct" (mirrors characterize_pdf D-06, kept verbatim): a
manifest Observable value that DIVERGES from the captured text is a MISS,
exactly like a value that is entirely ABSENT — this is the EVID-02 delta over
a Sentinel-style broken/blank check, which only ever notices "nothing there",
never "the wrong thing is there". A wrong value and a missing value are both
bugs, so both are reported the same way (present: False).

Arm split (deliberate, one-concern-per-file, mirrors characterize.py /
characterize_pdf.py): for the GREENFIELD arm, oracle precedence follows
Phase 5 (spec + design, 2-layer) and is already served by
`characterize_pdf.py` / `greenfield_gate.py`. This adapter is the PORT arm's
manifest-oracle sibling — do not merge the two.

Stdlib-only (mirrors manifest_gate.py's D-01): imports below are limited to
argparse/re/sys/pathlib. NO third-party package, no subprocess, no network —
the text source is always pre-captured and handed in via `--text-file`.

Usage:
    python3 characterize_manifest.py --manifest <path/to/route.manifest.md> --text-file <path>
    python3 characterize_manifest.py --repo <sdd-repo> --route <route> --text-file <path>
        (resolves manifest to <sdd-repo>/.port/<route>.manifest.md, mirroring
        manifest_gate.resolve_manifest_path)
    python3 characterize_manifest.py --manifest <path> --text-file <path> --screen <label>
        (optional filter -- assert only the rows belonging to one screen when
        the manifest covers multiple screens; default: assert every row)

Prints a VERDICT line and exits 1 if any manifest Observable is absent
(missing OR diverging) from the captured text, 0 if every row is present.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Whitespace-only (after strip -> "") or a lone dash/prolonged-sound-mark/minus
# counts as an empty cell -- mirrors manifest_gate.py / characterize_pdf.py.
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−"}


def _norm(cell: str) -> str:
    return cell.strip()


def _is_empty_cell(cell: str) -> bool:
    return _norm(cell) in EMPTY_CELL_MARKERS


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


def parse_manifest_rows(manifest_text: str, screen: str | None = None) -> list[dict]:
    """Parse the field-level Behavior Manifest shape (port arm) and return
    `{"label", "observable"}` per body row. Locates the table by an Observable
    column (needles `("observable", "oracle", "assert")`) — mirrors
    manifest_gate.py's obs_col resolution. A row/behavior label column is
    located by needles `("field", "observable", "hành vi", "behavior", "màn",
    "screen")`, falling back to the first cell when unresolvable.

    Optional `screen` filter: when a screen/target-like column is resolvable
    (needles `("màn", "screen", "target")`) and `screen` is given, only rows
    whose that cell matches `screen` (case-insensitive, stripped) are
    returned — mirrors characterize_pdf's target filter, but generalized
    since the port manifest may not always carry a screen column. When no
    such column is resolvable, the filter is a no-op (all rows returned).

    Reuses the manifest_gate/characterize_pdf pipe-table primitives — a
    linear, no-regex scan (T-02-01 DoS mitigation posture preserved).
    """
    lines = manifest_text.splitlines()
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
                o_col = _find_col(cells, ("observable", "oracle", "assert"))
                if o_col is not None:
                    header_idx = i
                    header_cells = cells
                    obs_col = o_col
                    break
        i += 1

    if header_idx is None or obs_col is None:
        return []

    label_col = _find_col(
        header_cells, ("field", "observable", "hành vi", "behavior", "màn", "screen")
    )
    screen_col = _find_col(header_cells, ("màn", "screen", "target"))

    rows: list[dict] = []
    j = header_idx + 1
    if j < n and _looks_like_table_row(lines[j]) and _is_separator_row(_split_row(lines[j])):
        j += 1

    while j < n:
        line = lines[j]
        if not _looks_like_table_row(line):
            break
        cells = _split_row(line)
        if _is_separator_row(cells):
            j += 1
            continue

        if screen is not None and screen_col is not None:
            cell_val = _norm(cells[screen_col]) if screen_col < len(cells) else ""
            if cell_val.lower() != _norm(screen).lower():
                j += 1
                continue

        if label_col is not None and label_col < len(cells):
            label = cells[label_col]
        else:
            label = cells[0] if cells else "?"
        observable = cells[obs_col] if obs_col < len(cells) else ""
        rows.append({"label": label, "observable": observable})
        j += 1

    return rows


_REGEX_OBSERVABLE = re.compile(r"^/(.*)/$")


def _observable_present(observable: str, text: str) -> bool:
    """Evaluate one Observable string against the captured text (copied
    verbatim from characterize_pdf.py's `_observable_present`).

    Supports (a) a plain expected substring/value (present-check) and (b) a
    `/regex/` form (re.search). Empty/whitespace-only Observables never
    count as present (nothing to assert would be a vacuous pass).
    """
    obs = observable.strip()
    if _is_empty_cell(obs):
        return False
    m = _REGEX_OBSERVABLE.match(obs)
    if m:
        pattern = m.group(1)
        return re.search(pattern, text) is not None
    return obs in text


def check_manifest_observables(text: str, rows: list[dict]) -> list[dict]:
    """PURE (no I/O): for each row, evaluate its Observable against `text`.

    "Present AND correct" (EVID-02, mirrors characterize_pdf.py's D-06)
    collapses to a single check: the exact expected value/pattern must be
    found in the captured text. A divergent value means the expected token is
    absent from `text` -> that row is reported as a MISS (present: False) —
    this is what makes a wrong value indistinguishable from a missing one, on
    purpose (both are bugs).

    Returns a list of {label, observable, present: bool} dicts, one per row,
    in input order.
    """
    results = []
    for row in rows:
        observable = row.get("observable", "")
        present = _observable_present(observable, text)
        results.append(
            {"label": row.get("label", "?"), "observable": observable, "present": present}
        )
    return results


def resolve_manifest_path(args: argparse.Namespace) -> Path:
    """Mirrors manifest_gate.py's resolve_manifest_path."""
    if args.manifest:
        return Path(args.manifest)
    return Path(args.repo) / ".port" / f"{args.route}.manifest.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="characterize_manifest",
        description=(
            "EVID-02 port-arm manifest oracle-assert adapter: for each "
            "Behavior Manifest row, assert its Observable value/pattern is "
            "present in a captured artifact's text -- a diverging value is a "
            "MISS just like a missing one (D-06/D-07)."
        ),
    )
    p.add_argument("--manifest", help="Path to the field-level Behavior Manifest .md file")
    p.add_argument("--repo", help="SDD repo root (used together with --route)")
    p.add_argument("--route", help="Route slug (used together with --repo)")
    p.add_argument(
        "--text-file",
        required=False,
        help="Path to the pre-captured text/JSON artifact to assert Observables against",
    )
    p.add_argument("--screen", help="Optional screen/target label filter (multi-screen manifest)")
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

    if not args.text_file:
        print("fail --text-file is required", file=sys.stderr)
        return 1

    manifest_path = resolve_manifest_path(args)
    if not manifest_path.exists() or manifest_path.is_dir():
        print("fail manifest not found", file=sys.stderr)
        return 1

    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read manifest: {e}", file=sys.stderr)
        return 1

    rows = parse_manifest_rows(manifest_text, screen=args.screen)
    if not rows:
        print("fail no Observable rows found in manifest", file=sys.stderr)
        return 1

    try:
        text = Path(args.text_file).read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read --text-file: {e}", file=sys.stderr)
        return 1

    results = check_manifest_observables(text, rows)
    absent = [r for r in results if not r["present"]]

    print("\n===== MANIFEST CHARACTERIZATION (Observable vs captured text) =====")
    print(f"  rows: {len(results)} | present: {len(results) - len(absent)} | absent: {len(absent)}")
    for r in absent:
        print(f'  MISS "{r["label"]}": expected {r["observable"]!r} — not found in captured text')

    print(f"\nVERDICT: {len(absent)} row(s) absent" if absent else "\nVERDICT: all rows present")
    return 1 if absent else 0


if __name__ == "__main__":
    sys.exit(main())
