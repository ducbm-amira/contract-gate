#!/usr/bin/env python3
"""QA fidelity-coverage gate — hard block trước khi cho `qa-pass` (D-20).

Song sinh với `manifest.py`: cùng contract stdlib-only + `pass`/`fail`
prefix + exit 0/1. Khác chỗ nó gác: KHÔNG cho đóng cycle ở step QA khi báo
cáo qa-verify chưa có **Fidelity Coverage Manifest** đầy đủ.

Vì sao có gate này (skills/qa-verify/SKILL.md D-20): QA hay báo "passed" khi
mới phủ 1 tầng (vụ sales-activity: PDF xong → sót screen → sót TEXT/label,
chỉ lòi khi bị người chọc). Checklist trong prompt là advisory → bị bỏ khi
vội. Gate này biến nó thành RUNNABLE hard block: verdict "QA passed" chỉ hợp
lệ khi ma trận `chiều × màn` có đủ chiều bắt buộc và KHÔNG ô nào bỏ trống.

Contract (mirror manifest.py D-03): pass → `pass <summary>` stdout, exit 0.
fail → `fail <one-line reason>` stderr, exit 1. Caller (pinrich-cycle QA step)
xử exit≠0 như QA-fail: không `done`, quay lại phủ nốt.

Định dạng REPORT.md mà gate đọc (qa-verify Phase 5 phải emit):

    <!-- coverage-matrix:start -->
    | màn | behavior | layout | feature | text | data |
    |-----|----------|--------|---------|------|------|
    | step5 | TC-B01 | TC-L02 | TC-F03 | TC-T04 | TC-D05 |
    | step7 | TC-B06 | N/A:trống | BOUNDARY:backend down | TC-T07 | N/A |
    <!-- coverage-matrix:end -->

Luật (D-20):
  1. Block delimiter tồn tại + có bảng bên trong (thiếu = drift, fail).
  2. Header có ĐỦ 5 chiều bắt buộc — đặc biệt `text` KHÔNG được thiếu cột
     (đây là tầng hay bị bỏ). Nhận diện theo substring EN/VN, thứ tự cột
     tự do, thêm cột phụ OK.
  3. Mọi ô (mọi màn × mọi chiều) phải ĐÃ ĐIỀN: hoặc 1 TC-ref, hoặc khai
     `N/A:...` / `BOUNDARY:...` / `SKIP:...`. Ô trống / `-` / `?` / `TODO`
     = chưa phủ → fail (nêu tên màn + chiều).

Format-forgiving như manifest.py: parser linear, chỉ str.split("|"), không
regex (không backtracking). Nó KHÔNG lint markdown, KHÔNG đòi header đúng
chữ/vị trí — chỉ bắt thiếu-chiều và ô-trống.

COV-01 (grouped-screen rejection, plan 06-01): một hàng gộp nhiều màn thành
1 label (vd `map+list`, `step5-9`) có thể "đủ ô" nhưng vẫn giấu gap per-màn —
1 TC-ref ở ô `feature` của `map+list` không chứng minh CẢ map lẫn list đều
đã test feature đó. Cột 0 (screen label) vì vậy bị soi thêm bởi
`_is_grouped_screen()`: một label bị coi là NHÓM GỘP (fail) khi nó chứa 1
trong các JOIN-separator rõ ràng `+`, `,`, `~`, `、`, `&`, token `all`/
`các màn`, HOẶC khớp shape numeric-range `<digits><sep><digits>` với
sep ∈ `-`/`~`/`～` (bắt `step5-9`/`step5～9`). Deliberately KHÔNG coi `-`
hay `/` là group signal ở dạng khác — `step-5` (không phải numeric-range cả
2 vế) và `deal/map` (route slug hợp lệ) phải pass, không false-positive.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

START = "<!-- coverage-matrix:start -->"
END = "<!-- coverage-matrix:end -->"

# Ô coi là CHƯA phủ (sau strip). Superset dash look-alikes + placeholder.
EMPTY_CELL_MARKERS = {"", "-", "—", "–", "ー", "−", "?", "??", "…", "..."}
PLACEHOLDER_WORDS = {"todo", "tbd", "wip", "n/a?", "x", "xx"}

# 5 chiều bắt buộc (D-20). Mỗi chiều = tuple substring (lower) EN/VN để dò header.
REQUIRED_DIMENSIONS = (
    ("behavior", ("behavior", "behav", "hành vi", "hanh vi")),
    ("layout", ("layout", "cấu trúc", "cau truc", "bố cục", "bo cuc")),
    ("feature", ("feature", "affordance", "chức năng", "chuc nang")),
    ("text", ("text", "copy", "label", "văn bản", "van ban", "chữ", "chu")),
    ("data", ("data", "dữ liệu", "du lieu", "logic")),
)


def _norm(cell: str) -> str:
    return cell.strip()


def _is_empty_cell(cell: str) -> bool:
    n = _norm(cell)
    return n in EMPTY_CELL_MARKERS or n.lower() in PLACEHOLDER_WORDS


def _looks_like_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
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


# COV-01: explicit multi-screen JOIN separators. Deliberately excludes "-"
# and "/" as blanket signals -- those are handled by the numeric-range check
# below (or, for "/", never flagged at all -- route slugs like "deal/map"
# legitimately use it, see docstring COV-01 note).
_GROUP_JOIN_SEPARATORS = ("+", ",", "~", "、", "&")
_GROUP_JOIN_WORDS = {"all", "các màn", "cac man"}
# Range separators allowed in the numeric-range shape "<digits><sep><digits>"
# (e.g. step5-9, step5~9, step5～9). "-" is ONLY a group signal in this exact
# shape -- a bare "-" elsewhere (kodate-estimate, step-5) must stay a pass.
_RANGE_SEPARATORS = ("-", "~", "～")


def _has_numeric_range(s: str) -> bool:
    """True iff `s` contains a contiguous `<digits><sep><digits>` shape for
    sep in _RANGE_SEPARATORS. Manual index scan -- no regex (T-02-01 no
    catastrophic-backtracking posture preserved)."""
    n = len(s)
    for sep in _RANGE_SEPARATORS:
        start = 0
        while True:
            pos = s.find(sep, start)
            if pos == -1:
                break
            k = pos - 1
            l_run = ""
            while k >= 0 and s[k].isdigit():
                l_run = s[k] + l_run
                k -= 1
            k = pos + 1
            r_run = ""
            while k < n and s[k].isdigit():
                r_run += s[k]
                k += 1
            if l_run and r_run:
                return True
            start = pos + 1
    return False


def _is_grouped_screen(screen: str) -> bool:
    """COV-01: True iff the screen-label cell names MORE THAN ONE screen
    (a grouped/gộp row), which would otherwise hide a per-individual-screen
    coverage gap behind a single "fully covered" row. See the module
    docstring's COV-01 note for the exact heuristic and its false-positive
    guards (`deal/map`, `step-5`, `kodate-estimate` must stay pass)."""
    s = _norm(screen)
    if not s:
        return False
    if any(sep in s for sep in _GROUP_JOIN_SEPARATORS):
        return True
    if s.lower() in _GROUP_JOIN_WORDS:
        return True
    return _has_numeric_range(s)


def _extract_block(text: str) -> str | None:
    i = text.find(START)
    if i < 0:
        return None
    j = text.find(END, i + len(START))
    if j < 0:
        return None
    return text[i + len(START):j]


def evaluate_coverage(text: str) -> tuple[bool, str]:
    """Core D-20 verdict. Returns (ok, reason) — one-line reason."""
    if not text or not text.strip():
        return False, "report empty"

    block = _extract_block(text)
    if block is None:
        return False, (
            "no coverage-matrix block found "
            "(<!-- coverage-matrix:start --> ... :end) — QA chưa lập ma trận chiều×màn (D-20)"
        )

    lines = block.splitlines()
    n = len(lines)

    # Header = dòng table đầu tiên không phải separator.
    header_idx: int | None = None
    header_cells: list[str] = []
    i = 0
    while i < n:
        if _looks_like_table_row(lines[i]):
            cells = _split_row(lines[i])
            if not _is_separator_row(cells):
                header_idx = i
                header_cells = cells
                break
        i += 1
    if header_idx is None:
        return False, "coverage-matrix block has no table header"

    # Cột 0 = màn/screen. Các cột còn lại = chiều.
    dim_cols: dict[str, int] = {}
    for idx in range(1, len(header_cells)):
        low = header_cells[idx].lower()
        for name, needles in REQUIRED_DIMENSIONS:
            if name in dim_cols:
                continue
            if any(nd in low for nd in needles):
                dim_cols[name] = idx

    missing = [name for name, _ in REQUIRED_DIMENSIONS if name not in dim_cols]
    if missing:
        return False, (
            f"coverage matrix thiếu chiều bắt buộc: {', '.join(missing)} "
            f"(D-20 — chiều 'text' đặc biệt không được bỏ)"
        )

    # Body rows.
    j = header_idx + 1
    if j < n and _looks_like_table_row(lines[j]) and _is_separator_row(_split_row(lines[j])):
        j += 1

    row_count = 0
    cell_count = 0
    while j < n:
        line = lines[j]
        if not _looks_like_table_row(line):
            j += 1
            continue
        cells = _split_row(line)
        if _is_separator_row(cells):
            j += 1
            continue
        row_count += 1
        screen = cells[0] if cells else f"row{row_count}"
        if _is_grouped_screen(screen):
            return False, (
                f'màn "{screen}" là nhóm gộp — tách 1 dòng / màn riêng (COV-01)'
            )
        for name, col in dim_cols.items():
            val = cells[col] if col < len(cells) else ""
            if _is_empty_cell(val):
                return False, (
                    f'màn "{screen or "?"}" × chiều "{name}" chưa phủ '
                    f'(điền TC-ref hoặc khai N/A:/BOUNDARY:)'
                )
            cell_count += 1
        j += 1

    if row_count == 0:
        return False, "coverage matrix không có dòng màn nào"

    return True, (
        f"{cell_count} ô đã phủ trên {row_count} màn × {len(dim_cols)} chiều (đủ text/label)"
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="coverage_gate",
        description=(
            "QA hard block (D-20): verify qa-verify REPORT.md có Fidelity "
            "Coverage Manifest đủ 5 chiều (gồm text) và mọi ô đã phủ."
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


def resolve_report_path(args: argparse.Namespace) -> Path | None:
    if args.report:
        return Path(args.report)
    if args.dir:
        d = Path(args.dir)
        cands = list(d.glob("*REPORT*.md")) + list(d.glob("*report*.md"))
        # Pick the newest report by mtime (the "latest report" intent), not the
        # alphabetically-last name — filenames carry no ordering guarantee.
        return max(cands, key=lambda p: p.stat().st_mtime) if cands else None
    return None


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

    ok, reason = evaluate_coverage(text)
    if ok:
        print(f"pass {reason}")
        return 0
    print(f"fail {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
