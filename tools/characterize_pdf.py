#!/usr/bin/env python3
"""PDF characterization adapter — the GREEN-02 exam mechanism (D-06/D-07, plan 05-02).

Where `characterize.py` treats LEGACY as the source of truth (does the React
runtime still show what Vue showed), this adapter treats the greenfield SPEC
(`.greenfield/<task>.spec.md`, the 2-layer oracle locked in 05-01) as the
source of truth, and the generated PDF as the artifact under exam. For every
spec row declared `target: pdf`, it asserts the row's Observable
value/pattern is PRESENT in the PDF's extracted text (via `pdftotext`) —
"present AND correct" (D-06): a value that is missing OR silently replaced by
a divergent value both make that row fail. This deliberately goes beyond "the
PDF opens" / render-to-image comparison — the exact "pass vì không crash"
shallowness this phase kills (memory: qa-fidelity-coverage-manifest, "diff
copy bằng pdftotext, đừng so bằng mắt").

D-07 (arm split, deliberate separate file): `target: web` Observables are
NOT this adapter's job — they are routed to the existing `characterize.py`
layer [A] as-is. A `--mode greenfield` merge into `characterize.py` was
explicitly NOT preferred (Claude's Discretion) to keep the legacy-oracle vs
spec-oracle logic readable as two files. This adapter only ever claims
`target: pdf` rows; `target: web`/`target: logic` rows are parsed but
excluded from the pdf check.

Stdlib-only (mirrors manifest_gate.py's D-01 / greenfield_gate.py's D-05):
imports below are limited to argparse/sys/subprocess/shutil/re/pathlib. NO
third-party package. `pdftotext` itself is an external system binary
(poppler-utils), not a Python package — it is invoked via `subprocess.run`
with LIST args (never `shell=True`, never a string-interpolated shell
command) to close the command-injection surface (T-05-04), and with a
bounded timeout to close the DoS surface on a malformed/huge PDF (T-05-05).

Usage:
    python3 characterize_pdf.py --spec <path/to/task.spec.md> --pdf <path/to/generated.pdf>
    python3 characterize_pdf.py --repo <target-repo> --task <task> --pdf <path/to/generated.pdf>
        (resolves spec to <target-repo>/.greenfield/<task>.spec.md)
    python3 characterize_pdf.py --spec <path> --text-file <path>
        (escape hatch: feed pre-extracted text instead of invoking pdftotext —
        mirrors characterize.py's --no-runtime; used by the test suite so it
        does not depend on a real PDF fixture existing)

Prints a VERDICT line and exits 1 if any `target: pdf` row's Observable is
absent from the extracted text, 0 if every row is present.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Whitespace-only (after strip -> "") or a lone dash/prolonged-sound-mark/minus
# counts as an empty cell — mirrors manifest_gate.py / greenfield_gate.py.
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−"}

PDFTOTEXT_TIMEOUT_SECONDS = 30


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


def extract_pdf_text(pdf_path: str) -> str:
    """Extract the PDF's text via the system `pdftotext` binary.

    LIST args only (`["pdftotext", pdf_path, "-"]`) — never `shell=True`,
    never a string-interpolated shell command (T-05-04, no shell-injection
    surface). A bounded timeout guards against a malformed/huge PDF hanging
    the process (T-05-05).
    """
    if shutil.which("pdftotext") is None:
        raise RuntimeError(
            "pdftotext not found on PATH — install poppler-utils "
            "(e.g. `apt install poppler-utils` / `brew install poppler`)"
        )
    result = subprocess.run(
        ["pdftotext", pdf_path, "-"],
        capture_output=True,
        text=True,
        timeout=PDFTOTEXT_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pdftotext failed on {pdf_path!r} (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def parse_pdf_rows(spec_text: str) -> list[dict]:
    """Parse the LOCKED greenfield spec shape (05-01: `target` + `Observable`
    columns) and return only the body rows whose `target` cell == "pdf"
    (case-insensitive). `target: web`/`target: logic` rows are excluded
    (D-07 — those belong to characterize.py layer [A] / a logic test, not
    this adapter). Each returned row carries its Behavior label and
    Observable assertion string.

    Reuses the manifest_gate/greenfield_gate pipe-table primitives — a
    linear, no-regex scan (mirrors T-02-01's DoS mitigation, T-05-06 here).
    """
    lines = spec_text.splitlines()
    n = len(lines)

    header_idx: int | None = None
    header_cells: list[str] = []
    target_col: int | None = None
    obs_col: int | None = None

    i = 0
    while i < n:
        line = lines[i]
        if _looks_like_table_row(line):
            cells = _split_row(line)
            if not _is_separator_row(cells):
                t_col = _find_col(cells, ("target",))
                o_col = _find_col(cells, ("observable", "assert"))
                if t_col is not None and o_col is not None:
                    header_idx = i
                    header_cells = cells
                    target_col = t_col
                    obs_col = o_col
                    break
        i += 1

    if header_idx is None or target_col is None or obs_col is None:
        return []

    behavior_col = _find_col(header_cells, ("behavior", "hành vi", "hanh vi"))

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

        target_cell = cells[target_col] if target_col < len(cells) else ""
        if _norm(target_cell).lower() == "pdf":
            if behavior_col is not None and behavior_col < len(cells):
                label = cells[behavior_col]
            else:
                label = cells[0] if cells else "?"
            observable = cells[obs_col] if obs_col < len(cells) else ""
            rows.append({"label": label, "observable": observable})
        j += 1

    return rows


_REGEX_OBSERVABLE = re.compile(r"^/(.*)/$")


def _observable_present(observable: str, text: str) -> bool:
    """Evaluate one Observable string against the extracted text.

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


def check_pdf_observables(text: str, rows: list[dict]) -> list[dict]:
    """PURE (no I/O): for each row, evaluate its Observable against `text`.

    "Present AND correct" (D-06) collapses to a single check: the exact
    expected value/pattern must be found in the extracted text. A divergent
    value in the PDF means the expected token is absent from `text` -> that
    row is reported as a MISS (present: False) — this is what makes a wrong
    value indistinguishable from a missing one, on purpose (both are bugs).

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


def resolve_spec_path(args: argparse.Namespace) -> Path:
    if args.spec:
        return Path(args.spec)
    return Path(args.repo) / ".greenfield" / f"{args.task}.spec.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="characterize_pdf",
        description=(
            "GREEN-02 PDF characterization adapter: for each greenfield spec "
            "row declared target=pdf, assert its Observable value/pattern is "
            "present in the PDF's pdftotext-extracted text (D-06/D-07)."
        ),
    )
    p.add_argument("--spec", help="Path to the .greenfield/<task>.spec.md file")
    p.add_argument("--repo", help="Target repo root (used together with --task)")
    p.add_argument("--task", help="Task slug (used together with --repo)")
    p.add_argument("--pdf", help="Path to the generated PDF artifact to extract text from")
    p.add_argument(
        "--text-file",
        help=(
            "Escape hatch: read pre-extracted text from this file instead of "
            "invoking pdftotext on --pdf (mirrors characterize.py --no-runtime)"
        ),
    )
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

    if not args.pdf and not args.text_file:
        print("fail either --pdf or --text-file is required", file=sys.stderr)
        return 1
    if args.pdf and args.text_file:
        print("fail specify --pdf OR --text-file, not both", file=sys.stderr)
        return 1

    spec_path = resolve_spec_path(args)
    if not spec_path.exists() or spec_path.is_dir():
        print("fail spec not found", file=sys.stderr)
        return 1

    try:
        spec_text = spec_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read spec: {e}", file=sys.stderr)
        return 1

    rows = parse_pdf_rows(spec_text)
    if not rows:
        print("fail no target=pdf rows found in spec", file=sys.stderr)
        return 1

    if args.text_file:
        try:
            text = Path(args.text_file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"fail could not read --text-file: {e}", file=sys.stderr)
            return 1
    else:
        try:
            text = extract_pdf_text(args.pdf)
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
            print(f"fail {e}", file=sys.stderr)
            return 1

    results = check_pdf_observables(text, rows)
    absent = [r for r in results if not r["present"]]

    print("\n===== PDF CHARACTERIZATION (target=pdf rows vs pdftotext extract) =====")
    print(f"  rows: {len(results)} | present: {len(results) - len(absent)} | absent: {len(absent)}")
    for r in absent:
        print(f'  MISS "{r["label"]}": expected {r["observable"]!r} — not found in PDF text')

    print(f"\nVERDICT: {len(absent)} row(s) absent" if absent else "\nVERDICT: all rows present")
    return 1 if absent else 0


if __name__ == "__main__":
    sys.exit(main())
