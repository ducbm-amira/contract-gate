#!/usr/bin/env python3
"""Fidelity gate — post-code hard block for the BUILD-vs-DESIGN pixel/token
layer (contract-gate gate #5, sibling of `golden_record.py` / `manifest.py` /
`greenfield.py` / `data_binding.py`).

Where `golden-record` catches "the wiring pulled the wrong data", this gate
catches "the built screen doesn't actually look like the design" — colors,
tokens, layout, affordances, pixels. The heavy lifting (render design + built
screen with the same pinned Chromium, pair nodes, run ΔE2000/token/affordance/
pixel checks, bucket the findings) is NOT reimplemented here — it already
exists as its own tool, `design-fidelity-gate` (separate repo, own venv,
Playwright/pixelmatch/coloraide deps), invoked as `python -m verdict --screen
<id> --out <report.json>`.

FID-01 (stdlib-only, hard verdict — mirrors golden_record.py's GOLD-01):
imports below are limited to argparse/json/sys/pathlib plus the sibling
`contract_gate.tableparse` module (also stdlib-only). NO third-party
package, NO subprocess, NO Playwright/pixelmatch/coloraide import here — this
gate NEVER runs the pixel-diff itself (that would pull design-fidelity-gate's
whole dependency stack into contract-gate's zero-dep CLI, and would just
relocate the "trust me" problem the way golden_record.py's GOLD-01 already
argues against for DB/browser driving). It only grades an ALREADY-WRITTEN
bucketed report JSON — produced by a prior, separate `python -m verdict` run
(the `/pinrich-cycle` FIDELITY step, or a human/agent running it by hand) —
the same "grade the recorded evidence, don't go fetch it yourself" posture as
golden_record.py. On success prints `pass <summary>` to stdout and exits 0.
On any failure prints `fail <one-line reason>` to stderr and exits 1.

FID-02 (what counts as a qualifying table): a markdown pipe table whose
header row has BOTH a column recognizable as "Screen" AND a **distinct**
column recognizable as "Report" (the path to that screen's `python -m
verdict --out` JSON), resolved as a mutually-exclusive pair (GOLD-06
exclusion guard via `tableparse.find_col`, ported 2026-07-11 — a single
"Screen report" header cell now disqualifies the table loudly instead of
resolving both fields to it). An optional "Notes" column is carried through
only for the human, never graded.

FID-03 (the gate — per row, in order):
  1. Report cell must be non-empty/non-placeholder — an unfilled Report cell
     means `python -m verdict` was never run for this screen, so there is no
     evidence yet that build matches design.
  2. The report path must resolve to a real, readable file.
  3. The file must parse as JSON and have a top-level `overall` key — the
     exact shape `design-fidelity-gate/src/report/buckets.py::
     build_bucketed_report` writes (`{"overall": "PASS"|"FAIL", "buckets":
     {...}, "findings": [...]}`). Anything else is a malformed/foreign
     report, not a fidelity pass.
  4. `overall` must be exactly "PASS". "FAIL" is reported together with the
     names of every bucket whose own verdict is "FAIL", so the failure
     reason points straight at which dimension drifted (color/font/size/
     position/radius/shadow/affordance/pixel/geometry/other) instead of
     forcing a re-open of the JSON.
  5. every qualifying table must have at least one body row — a header-only
     fidelity table is an ungraded claim, not a pass (fixed 2026-07-11;
     before, a bare header passed with "0 screen(s) fidelity-verified").
A cell that is whitespace-only, a lone dash look-alike, or a placeholder
word (?/TODO/TBD/WIP/…) counts as UNFILLED — the family-wide
`tableparse.is_empty_cell` rule, now genuinely identical across all six
gates because it IS the same function.

FID-04 (relative report paths): a Report cell that is not already absolute
is resolved relative to the *contract file's own directory* (not the CWD the
gate happens to be invoked from) — so a contract file can be committed
alongside the report it pins and stay portable across checkouts. When
`evaluate()`/`findings()` are called directly on bare text with no `path`
(e.g. from a unit test), a relative Report cell resolves against the CWD.

FID-05 (multi-table files — scan the WHOLE file, ported preventively from the
identical D-07 bug already fixed once in `greenfield.py` and once in
`manifest.py`): every qualifying table is graded; parsing is delegated to
`tableparse.iter_tables`, which also handles tables ABUTTING each other with
no blank line in between (the D-07 residue — false-PASS surface). Do not
"optimize" this into an early return.

FID-06 (decision, deliberately NOT enforced here): this gate does not check
that the report is FRESH — i.e. that it was regenerated against the current
commit/build rather than left over from a stale run days ago. The bucketed
report JSON itself carries no build fingerprint to check against (verified:
`design-fidelity-gate/src/verdict/__main__.py` writes only `overall` /
`buckets` / `findings`, no screen id, timestamp, or content hash). Closing
that gap belongs to the caller's own discipline (e.g. `/pinrich-cycle`'s
FIDELITY step runs `python -m verdict` immediately before gating, so the
report is fresh by construction) or to a future report-schema change in
design-fidelity-gate itself — not to a stdlib text-parsing gate re-deriving
build identity it has no way to verify. This comment is the record that
FID-06 was decided, not silently dropped.

FID-07 (draft asymmetry, mirrors golden_record.py's GOLD-05): unlike
`data-binding`/`greenfield`/`manifest`, this gate is NOT spec-inferable — an
LLM reading a spec/design has no way to know whether `python -m verdict` has
actually been run for a screen, or what it said. DRAFT_GUIDANCE instructs
leaving the Report cell as `?` unless the source material given to the
drafting agent explicitly includes the report path/content (e.g. it was
just run in the same session).

Usage:
    python3 -m contract_gate.gates.fidelity --contract <path/to/x.fidelity.md>
    python3 -m contract_gate.gates.fidelity --repo <target-repo> --screen <screen-id>
        (resolves to <target-repo>/.port/<screen-id>.fidelity.md)
Exactly one of the two forms is required.

FID-08 (deliberately narrow GLOBS, no generic `*.contract.md` catch-all —
mirrors manifest.py/greenfield.py, NOT data_binding.py/golden_record.py):
name a real contract file `<screen>.fidelity.md` (the init scaffold is
`example.fidelity.md`, which the GLOBS DO match — an unfilled scaffold
fails loudly instead of hiding under a name no gate owns).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .. import tableparse as tp
except ImportError:  # standalone `python3 contract_gate/gates/fidelity.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from contract_gate import tableparse as tp

# Shared family-wide helpers (see tableparse.py). Local aliases keep the
# historical names used throughout this module.
EMPTY_CELL_MARKERS = tp.EMPTY_CELL_MARKERS
PLACEHOLDER_WORDS = tp.PLACEHOLDER_WORDS
_norm = tp.norm
_is_empty_cell = tp.is_empty_cell
_looks_like_table_row = tp.looks_like_table_row
_split_row = tp.split_row
_is_separator_row = tp.is_separator_row
_find_col = tp.find_col

# Header-detection needles (lowercase substrings, EN/VN).
SCREEN_NEEDLES = ("screen", "màn", "man hinh", "màn hình", "trang", "page")
REPORT_NEEDLES = ("report", "báo cáo", "bao cao", "verdict", "json")
NOTES_NEEDLES = ("note", "notes", "ghi chú", "ghi chu")

# The exact bucket names design-fidelity-gate's build_bucketed_report emits
# (TOKEN_BUCKETS + RESERVED_BUCKETS, plus the catch-all "other") — used only
# to sanity-order the failing-buckets list in a failure reason, never to
# reject an unrecognized bucket name (a future engine bucket must not break
# this gate).
_KNOWN_BUCKET_ORDER = (
    "color", "font", "size", "position", "radius", "shadow",
    "affordance", "pixel", "geometry", "interaction", "other",
)

# Optional delimiter — when present, only the enclosed block(s) are scanned
# (EVERY start..end pair, not just the first — tableparse.extract_scope).
START = "<!-- fidelity:start -->"
END = "<!-- fidelity:end -->"


def _resolve_header(cells: list[str]) -> dict | None:
    """FID-02: qualify iff the header has a Screen column AND a DISTINCT
    Report column (GOLD-06 exclusion guard)."""
    screen_col = _find_col(cells, SCREEN_NEEDLES)
    if screen_col is None:
        return None
    report_col = _find_col(cells, REPORT_NEEDLES, exclude=frozenset({screen_col}))
    if report_col is None:
        return None
    return {"screen_col": screen_col, "report_col": report_col}


def _row_label(cells: list[str], screen_col: int | None, idx: int) -> str:
    screen = _norm(cells[screen_col]) if screen_col is not None and screen_col < len(cells) else ""
    return f'screen "{screen}"' if screen else f"row {idx}"


def _resolve_report_path(cell: str, base_dir: Path | None) -> Path:
    p = Path(_norm(cell))
    if p.is_absolute() or base_dir is None:
        return p
    return base_dir / p


def _grade_report(report_path: Path, label: str) -> str | None:
    """Returns a failure reason, or None if the report says overall=PASS."""
    if not report_path.exists() or report_path.is_dir():
        return f"{label} fidelity report not found at {report_path} — has `python -m verdict` been run for it yet?"
    try:
        raw = report_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"{label} fidelity report at {report_path} could not be read: {e}"
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"{label} fidelity report at {report_path} is not valid JSON: {e}"
    if not isinstance(report, dict) or "overall" not in report:
        return (
            f"{label} fidelity report at {report_path} has no 'overall' key — "
            f"not a design-fidelity-gate bucketed report"
        )
    overall = report.get("overall")
    if overall == "PASS":
        return None
    if overall != "FAIL":
        return f"{label} fidelity report at {report_path} has unexpected overall={overall!r} (expected PASS/FAIL)"
    buckets = report.get("buckets", {})
    failing = []
    if isinstance(buckets, dict):
        failing = [name for name, b in buckets.items() if isinstance(b, dict) and b.get("verdict") == "FAIL"]
        failing.sort(key=lambda n: _KNOWN_BUCKET_ORDER.index(n) if n in _KNOWN_BUCKET_ORDER else len(_KNOWN_BUCKET_ORDER))
    bucket_note = f" — failing bucket(s): {', '.join(failing)}" if failing else ""
    return f"{label} fidelity FAIL (see {report_path}){bucket_note}"


def _analyze(text: str, base_dir: Path | None) -> tuple[list[str], str]:
    """Single linear pass backing both evaluate() (fail-fast) and findings()
    (collect-all). Returns (findings, summary): non-empty findings = fail."""
    if not text or not text.strip():
        return ["fidelity contract file empty"], ""

    lines = tp.extract_scope(text, START, END).splitlines()
    tables = tp.iter_tables(lines, _resolve_header)

    if not tables:
        return [
            "no fidelity table found (cần bảng có cột Screen + Report — FID-02)"
        ], ""

    fs: list[str] = []
    rows_total = 0
    for t_idx, table in enumerate(tables):
        screen_col = table["screen_col"]
        report_col = table["report_col"]
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
            label = _row_label(cells, screen_col, row_idx)

            report_cell = cells[report_col] if report_col < len(cells) else ""
            if _is_empty_cell(report_cell):
                fs.append(
                    f"{label} has no Report path — run `python -m verdict --screen <id> --out <path>` "
                    f"first (FID-03: no evidence yet that build matches design)"
                )
                j += 1
                continue

            report_path = _resolve_report_path(report_cell, base_dir)
            reason = _grade_report(report_path, label)
            if reason:
                fs.append(reason)

            j += 1

        if row_idx == 0:
            # FID-03.5: a header-only table is an ungraded claim, not a pass.
            fs.append(f"{table_label} has a fidelity table header but no rows")

    summary = f"{rows_total} screen(s) fidelity-verified across {len(tables)} table(s)"
    return fs, summary


def evaluate_contract(text: str, base_dir: Path | None = None) -> tuple[bool, str]:
    fs, summary = _analyze(text, base_dir)
    if fs:
        return False, fs[0]
    return True, summary


def findings(text: str, path: Path | None = None) -> list[str]:
    """ALL failure reasons (empty = pass)."""
    base_dir = path.parent if path is not None else None
    return _analyze(text, base_dir)[0]


# --------------------------------------------------------------------------
# Gate descriptor — consumed by the contract-gate CLI registry.
# --------------------------------------------------------------------------

KEY = "fidelity"
TITLE = "Build-vs-design pixel/token fidelity"
# FID-08: narrow on purpose — no "*.contract.md" catch-all (see module docstring).
GLOBS = ("*.fidelity.md",)


def contains_fidelity_table(text: str) -> bool:
    """True iff `text` has at least one qualifying table (header with BOTH a
    Screen and a DISTINCT Report column) — lets the CLI skip files that
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
    return contains_fidelity_table(text)


def evaluate(text: str, path: Path | None = None) -> tuple[bool, str]:
    base_dir = path.parent if path is not None else None
    return evaluate_contract(text, base_dir)


DRAFT_GUIDANCE = """\
Draft a Fidelity verification table: one row per screen, pinning the path to
that screen's `python -m verdict --out <path>` bucketed report JSON.

CRITICAL — this gate is fundamentally different from a spec-derived contract:
- Report MUST come from an ACTUAL `python -m verdict --screen <id> --out
  <path>` run against design-fidelity-gate — NEVER infer or guess a path
  that plausibly "should" exist. If the --source material given to you does
  not explicitly show that command having been run (or its JSON output)
  for this screen, leave Report as `?`.
- Do not fabricate a report's content or its verdict — this gate reads the
  report FILE itself; a hand-typed "PASS" in this table means nothing and
  will be ignored by the check.
- One row per screen that needs a fidelity gate; add a Notes column only if
  useful context exists (e.g. which /pinrich-cycle step produced the report).

NEVER invent a plausible-looking report path to make the gate pass — a `?`
is correct and expected here far more often than in other gates; it marks
exactly the step (actually run the verdict tool against the built screen)
that still has to happen before this contract means anything.

Output ONLY the completed markdown contract below (keep the table shape); no
prose before or after."""


TEMPLATE = """\
# Fidelity verification — <feature/task>

> Pin, cho MỖI màn cần gate fidelity, đường dẫn report JSON do
> `python -m verdict --screen <id> --out <path>` sinh ra thật. KHÔNG tự bịa
> đường dẫn hay verdict — gate này tự mở report thật để chấm, chữ "PASS" gõ
> tay ở đây không có tác dụng gì.

<!-- fidelity:start -->
| Screen | Report | Notes |
|--------|--------|-------|
| <screen-id> | <path/to/screen-id.report.json> | <pinrich-cycle FIDELITY step, hoặc chạy tay> |
<!-- fidelity:end -->
"""


def resolve_contract_path(args: argparse.Namespace) -> Path:
    if args.contract:
        return Path(args.contract)
    return Path(args.repo) / ".port" / f"{args.screen}.fidelity.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fidelity_gate",
        description=(
            "Post-code hard block (FID-01): verify every screen pinned in a "
            "fidelity contract has an already-written design-fidelity-gate "
            "bucketed report and that report's overall verdict is PASS."
        ),
    )
    p.add_argument("--contract", help="Path to the fidelity contract .md file")
    p.add_argument("--repo", help="Target repo root (used together with --screen)")
    p.add_argument("--screen", help="Screen id (used together with --repo)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    has_contract = bool(args.contract)
    has_repo_screen = bool(args.repo) and bool(args.screen)
    has_partial_repo_screen = bool(args.repo) != bool(args.screen)

    if has_contract and (args.repo or args.screen):
        print("fail specify --contract OR --repo+--screen, not both", file=sys.stderr)
        return 1
    if has_partial_repo_screen:
        print("fail --repo and --screen must be given together", file=sys.stderr)
        return 1
    if not has_contract and not has_repo_screen:
        print("fail either --contract or both --repo and --screen are required", file=sys.stderr)
        return 1

    path = resolve_contract_path(args)
    if not path.exists() or path.is_dir():
        print("fail fidelity contract file not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read fidelity contract: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate_contract(text, path.parent)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
