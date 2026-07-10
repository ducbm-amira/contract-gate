#!/usr/bin/env python3
"""Evidence gate — EVID-01 eyeball-downgrade hard block (D-05, plan 06-01).

Song sinh với `coverage.py`/`manifest.py`: cùng contract stdlib-only
+ `pass`/`fail` prefix + exit 0/1. Đây là dạng RUNNABLE của luật D-05
(Evidence-grounding) hiện đang chỉ sống ở dạng prose trong
`skills/qa-verify/SKILL.md` — mọi dòng ✅/PASS ở REPORT.md PHẢI có evidence cụ
thể đính kèm (Method + Screenshot/Note ở bảng "Kịch bản đã verify"; Evidence ở
bảng "Manifest Trace"), nếu không PHẢI hạ xuống NOT-verified trước khi tính
verdict. Gate này chặn đúng lỗi "PASS từ tường thuật/lời kể suông" — tester
tick ✅ bằng mắt mà không đính kèm gì (EVID-01/SC1).

Contract (mirror manifest.py/coverage.py D-03): pass -> `pass <summary>`
stdout, exit 0. fail -> `fail <one-line reason>` stderr, exit 1. Caller
(pinrich-cycle QA step) xử exit!=0 như QA-fail: không `done`, quay lại
`/qa-verify` phủ evidence rồi chạy lại gate.

Hai bảng gate scan (skills/qa-verify/SKILL.md:519-541):
  - "Kịch bản đã verify" — header có cột Kết quả + cột Method. Dòng ✅/PASS
    (kể cả PASS-WEAK) PHẢI có Method KHÔNG rỗng VÀ ít nhất một trong
    Screenshot/Note KHÔNG rỗng.
  - "Manifest Trace" (RTM) — header có cột Verdict + cột Evidence, KHÔNG có
    cột Method. Dòng ✅/PASS PHẢI có Evidence KHÔNG rỗng.

Dòng exempt khỏi luật trên (không phải "subject"): kết quả rỗng, hoặc chứa
❌ / FAIL / NOT-verified / BLOCKED — một dòng khai KHÔNG pass thì không bị bắt
thiếu evidence (chỉ ✅/PASS "nhìn" mới là cái bị hạ).

Fail-closed (T-06-01): nếu một bảng có cột "Kết quả"/Verdict nhận diện được
nhưng KHÔNG tìm thấy cả cột Method lẫn cột Evidence nào trong chính bảng đó,
mọi dòng ✅/PASS trong bảng đó bị coi là fail — gate KHÔNG BAO GIỜ pass vì
"không chấm được" (never a vacuous pass). Các bảng khác trong report không có
cột Kết quả/Verdict nào cả (Sentinel, Domain format, ...) không phải bảng
evidence và bị bỏ qua hoàn toàn.

Format-forgiving như các gate anh em: parser linear, chỉ str.split("|"),
không regex (T-06-02, DoS mitigation) — cột được dò bằng substring
case-insensitive, thứ tự cột / header EN-VN tự do.

Usage:
    python3 evidence.py --report <path/to/REPORT.md>
    python3 evidence.py --dir <~/Developer/qa-report/<task>>  (dò REPORT*.md mới nhất)
Đúng 1 trong 2 form.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---- format-forgiving pipe-table primitives (copied verbatim from
# manifest.py — sibling-gate contract, do not diverge) ----

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


# ---- evidence_gate-specific column needles ----

RESULT_NEEDLES = ("kết quả", "ket qua", "result", "verdict")
METHOD_NEEDLES = ("method",)
EVIDENCE_NEEDLES = ("evidence",)
SCREENSHOT_NEEDLES = ("screenshot",)
NOTE_NEEDLES = ("note", "ghi chú", "ghi chu")
LABEL_NEEDLES = (
    "tc-id",
    "tc id",
    "kịch bản",
    "kich ban",
    "manifest row",
    "hành vi",
    "hanh vi",
)


def _iter_tables(lines: list[str]):
    """Yield (header_cells, body_start_idx, body_end_idx) for every markdown
    pipe table found in `lines`, in document order. Linear single pass, no
    regex (T-06-02)."""
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        if _looks_like_table_row(line):
            cells = _split_row(line)
            if not _is_separator_row(cells):
                header_cells = cells
                j = i + 1
                if (
                    j < n
                    and _looks_like_table_row(lines[j])
                    and _is_separator_row(_split_row(lines[j]))
                ):
                    j += 1
                body_start = j
                while j < n and _looks_like_table_row(lines[j]):
                    j += 1
                yield header_cells, body_start, j
                i = j
                continue
        i += 1


def _is_subject_row(result_cell: str) -> bool:
    """A row is "subject" to the evidence rule iff its result cell claims a
    pass (✅ or the token PASS, including PASS-WEAK). Exempt: empty, ❌, FAIL,
    NOT-verified, BLOCKED — only a claimed pass can be downgraded."""
    c = _norm(result_cell)
    if not c:
        return False
    if "❌" in c:
        return False
    low = c.lower()
    if any(m in low for m in ("fail", "not-verified", "not verified", "blocked")):
        return False
    return "✅" in c or "pass" in low


def evaluate_evidence(text: str) -> tuple[bool, str]:
    """Core D-05 verdict over a qa-verify REPORT.md. Returns (ok, reason).

    Scans every pipe table in the document. A table is:
      - type A ("Kịch bản đã verify") when it has BOTH a result column and a
        Method column -> subject rows need Method non-empty AND (Screenshot
        OR Note) non-empty.
      - type B ("Manifest Trace") when it has a result/verdict column and an
        Evidence column but NO Method column -> subject rows need Evidence
        non-empty.
      - type C (ungradeable) when it has a result column but NEITHER a
        Method NOR an Evidence column -> any subject row in it fails
        fail-closed (T-06-01), it is never silently skipped.
    Tables with no result column at all (Sentinel, Domain format, ...) are
    not evidence tables and are ignored entirely.
    """
    if not text or not text.strip():
        return False, "report empty"

    lines = text.splitlines()
    subject_count = 0
    table_count = 0

    for header_cells, body_start, body_end in _iter_tables(lines):
        result_col = _find_col(header_cells, RESULT_NEEDLES)
        if result_col is None:
            continue  # not an evidence-bearing table (Sentinel/Domain/etc.)

        method_col = _find_col(header_cells, METHOD_NEEDLES)
        evidence_col = _find_col(header_cells, EVIDENCE_NEEDLES)
        screenshot_col = _find_col(header_cells, SCREENSHOT_NEEDLES)
        note_col = _find_col(header_cells, NOTE_NEEDLES)
        label_col = _find_col(header_cells, LABEL_NEEDLES)

        if method_col is not None:
            table_kind = "A"
        elif evidence_col is not None:
            table_kind = "B"
        else:
            table_kind = "C"  # fail-closed: no gradeable column found

        table_count += 1
        row_count = 0
        for idx in range(body_start, body_end):
            cells = _split_row(lines[idx])
            if _is_separator_row(cells):
                continue
            row_count += 1
            result_cell = cells[result_col] if result_col < len(cells) else ""
            if not _is_subject_row(result_cell):
                continue
            subject_count += 1
            if label_col is not None and label_col < len(cells):
                label = cells[label_col]
            else:
                label = cells[0] if cells else "?"

            if table_kind == "A":
                method_cell = cells[method_col] if method_col < len(cells) else ""
                screenshot_cell = (
                    cells[screenshot_col]
                    if screenshot_col is not None and screenshot_col < len(cells)
                    else ""
                )
                note_cell = (
                    cells[note_col] if note_col is not None and note_col < len(cells) else ""
                )
                if _is_empty_cell(method_cell):
                    return False, f'row {row_count} ("{label}") ✅ nhưng thiếu Method'
                if _is_empty_cell(screenshot_cell) and _is_empty_cell(note_cell):
                    return False, (
                        f'row {row_count} ("{label}") ✅ nhưng thiếu Evidence '
                        "(Screenshot/Note)"
                    )
            elif table_kind == "B":
                evidence_cell = cells[evidence_col] if evidence_col < len(cells) else ""
                if _is_empty_cell(evidence_cell):
                    return False, f'row {row_count} ("{label}") ✅ nhưng thiếu Evidence'
            else:  # table_kind == "C" -- fail-closed
                return False, (
                    f'row {row_count} ("{label}") ✅ nhưng không tìm thấy cột '
                    "Method/Evidence trong bảng (fail-closed — D-05/T-06-01)"
                )

    if subject_count == 0:
        return True, f"0 dòng ✅/PASS cần chấm (đã quét {table_count} bảng)"
    return True, (
        f"{subject_count} dòng ✅/PASS đều có Method/Evidence hợp lệ "
        f"(đã quét {table_count} bảng)"
    )


def resolve_report_path(args: argparse.Namespace) -> Path | None:
    """Reused verbatim from coverage.py — same --report/--dir resolution
    contract (evidence gate reads the same REPORT.md, newest-by-mtime)."""
    if args.report:
        return Path(args.report)
    if args.dir:
        d = Path(args.dir)
        cands = list(d.glob("*REPORT*.md")) + list(d.glob("*report*.md"))
        return max(cands, key=lambda p: p.stat().st_mtime) if cands else None
    return None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="evidence_gate",
        description=(
            "QA hard block (EVID-01/D-05): mọi dòng ✅/PASS ở REPORT.md phải "
            "có Method + Evidence (Kịch bản đã verify) hoặc Evidence "
            "(Manifest Trace) — không cho eyeball-pass."
        ),
    )
    p.add_argument("--report", help="Path tới REPORT.md của qa-verify")
    p.add_argument(
        "--dir",
        help=(
            "Thư mục artifact qa-report (~/Developer/qa-report/<task>) — chọn "
            "REPORT*.md mới nhất theo mtime"
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if bool(args.report) == bool(args.dir):
        print("fail specify exactly one of --report or --dir", file=sys.stderr)
        return 1

    path = resolve_report_path(args)
    if path is None or not path.exists() or path.is_dir():
        print("fail report not found", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"fail could not read report: {e}", file=sys.stderr)
        return 1

    ok, reason = evaluate_evidence(text)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
