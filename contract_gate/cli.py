#!/usr/bin/env python3
"""contract-gate — a project-agnostic pre-coding contract gate.

Enforces the discipline **understand → contract → verify** *before* code is
written, so vibe-coding can't amplify an ambiguous input into confident-but-
wrong code. Point it at a repo; it autodiscovers contract files, runs every
applicable gate, and returns a single verdict + exit code — drop-in for CI,
a pre-commit hook, or an agent's pre-BUILD step.

Exit codes (the load-bearing contract external wiring depends on):
    0  every graded contract passed (a directory scan that finds zero
       contract files also exits 0 — "nothing to gate" is not an error;
       callers like /pinrich-cycle's ADVISORY step rely on that)
    1  at least one contract failed a gate, OR an explicitly named FILE
       argument was claimed by no gate (you pointed at it — silence would
       be a false pass)
    2  BLOCKED — a file could not be read/decoded or a gate crashed; the
       verdict is not trustworthy and must not be read as pass OR fail

Loud-over-silent: files that match a gate's GLOBS but whose content no gate
recognizes (`applies()` false for all) are listed as per-file warnings —
they are NOT graded and NOT failed, but never silently invisible either.

Stdlib-only, zero runtime dependencies. Each gate lives in `contract_gate/
gates/` and is registered in `gates/__init__.py::REGISTRY`.

    contract-gate check [path]        # gate all contracts under path (default .)
    contract-gate check file.md       # gate ONE file (no gate claims it => exit 1)
    contract-gate check . --format json
    contract-gate init [path]         # scaffold starter contract templates
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
from pathlib import Path

from . import __version__
from .gates import REGISTRY

GATES_BY_KEY = {g.KEY: g for g in REGISTRY}

# Cap per-source material fed into a draft prompt so a huge design.html can't
# blow up the context; the head carries the structural signal we need.
_SOURCE_CHAR_CAP = 60_000

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_BLOCKED = 2


def _discover(root: Path, globs: tuple[str, ...]) -> list[Path]:
    """All files under `root` matching any of `globs`, de-duped and sorted."""
    seen: set[Path] = set()
    for g in globs:
        for p in root.rglob(g):
            if p.is_file():
                seen.add(p)
    return sorted(seen)


def _read_text(f: Path) -> tuple[str | None, str | None]:
    """(text, error): error is a BLOCKED reason when the file can't be read
    or decoded. UnicodeDecodeError is NOT an OSError — before 2026-07-11 a
    single non-UTF-8 file crashed the whole run with a traceback, aborting
    every not-yet-graded file and emitting no JSON at all."""
    try:
        return f.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, f"BLOCKED — could not read/decode: {e}"


def _blocked(gate_key: str, f: Path, reason: str) -> dict:
    return {"gate": gate_key, "file": f, "ok": False, "blocked": True, "reason": reason}


def _safe_applies(gate, f: Path, text: str, results: list[dict]) -> bool:
    """applies() wrapped so a crash surfaces as a BLOCKED result instead of
    aborting the run (crash != silent skip, crash != fail)."""
    try:
        return gate.applies(text)
    except Exception as e:
        results.append(_blocked(gate.KEY, f, f"BLOCKED — applies() crashed: {e.__class__.__name__}: {e}"))
        return False


def _grade(gate, f: Path, text: str, all_mode: bool) -> list[dict]:
    """Grade one (gate, file) pair; a gate crash becomes a BLOCKED result
    (exit 2) — never a silent skip, never a plain fail."""
    try:
        if all_mode and hasattr(gate, "findings"):
            fs = gate.findings(text, f)
            if fs:
                return [
                    {"gate": gate.KEY, "file": f, "ok": False, "blocked": False, "reason": r}
                    for r in fs
                ]
            _ok, reason = gate.evaluate(text, f)  # pass summary
            return [{"gate": gate.KEY, "file": f, "ok": True, "blocked": False, "reason": reason}]
        ok, reason = gate.evaluate(text, f)
        return [{"gate": gate.KEY, "file": f, "ok": ok, "blocked": False, "reason": reason}]
    except Exception as e:
        return [_blocked(gate.KEY, f, f"BLOCKED — gate crashed: {e.__class__.__name__}: {e}")]


def _glob_matching_gates(name: str) -> list[str]:
    return [g.KEY for g in REGISTRY if any(fnmatch.fnmatch(name, pat) for pat in g.GLOBS)]


def _check_single_file(f: Path, fmt: str, all_mode: bool) -> int:
    """`check <file>`: the user pointed at ONE file explicitly. It is graded
    by every gate whose applies() claims it, GLOBS regardless (an explicit
    argument outranks filename conventions). If NO gate claims it, that is a
    loud exit-1 failure with a diagnosis — before 2026-07-11 this path fell
    through rglob() (a file has no children), printed 'no contract files
    found' and exited 0: a failing contract 'passed' at the CLI level."""
    results: list[dict] = []
    text, err = _read_text(f)
    if err is not None:
        results.append(_blocked("-", f, err))
        return _report(results, [], fmt, f.parent)

    for gate in REGISTRY:
        if _safe_applies(gate, f, text, results):
            results.extend(_grade(gate, f, text, all_mode))

    if not results:
        matching = _glob_matching_gates(f.name)
        if matching:
            detail = (
                f"its name matches GLOBS of gate(s) [{', '.join(matching)}] but its content "
                f"has no table those gates recognize"
            )
        else:
            known = ", ".join(p for g in REGISTRY for p in g.GLOBS)
            detail = f"its name matches no gate's GLOBS (known patterns: {known}) and no gate recognizes its content"
        results.append({
            "gate": "-", "file": f, "ok": False, "blocked": False,
            "reason": f"no gate claims this file — {detail}; NOT graded "
                      f"(explicitly named file, so silence would be a false pass)",
        })
    return _report(results, [], fmt, f.parent)


def cmd_check(path: str, fmt: str, all_mode: bool = False) -> int:
    root = Path(path)
    if not root.exists():
        print(f"block path not found: {path}", file=sys.stderr)
        return EXIT_BLOCKED
    if root.is_file():
        return _check_single_file(root, fmt, all_mode)

    results: list[dict] = []
    matched: dict[Path, set[str]] = {}   # every file some gate's GLOBS matched
    claimed: set[Path] = set()           # files at least one gate applied to
    unreadable: set[Path] = set()

    for gate in REGISTRY:
        for f in _discover(root, gate.GLOBS):
            matched.setdefault(f, set()).add(gate.KEY)
            if f in unreadable:
                continue
            text, err = _read_text(f)
            if err is not None:
                results.append(_blocked(gate.KEY, f, err))
                unreadable.add(f)
                claimed.add(f)  # already reported as BLOCKED; don't also warn
                continue
            # A gate only judges files it owns — a shared name like *.contract.md
            # that holds a different contract is skipped (and warned about below
            # if NO gate ends up claiming it).
            if not _safe_applies(gate, f, text, results):
                continue
            claimed.add(f)
            results.extend(_grade(gate, f, text, all_mode))

    warnings: list[str] = []
    for f in sorted(matched):
        if f not in claimed:
            gates_str = ", ".join(sorted(matched[f]))
            warnings.append(
                f"{_rel(f, root)}: matched GLOBS of gate(s) [{gates_str}] but no gate "
                f"claimed its content (applies() == False) — NOT graded"
            )

    return _report(results, warnings, fmt, root)


def _rel(f: Path, root: Path):
    try:
        return f.relative_to(root)
    except ValueError:
        return f


def _report(results: list[dict], warnings: list[str], fmt: str, root: Path) -> int:
    failed = [r for r in results if not r["ok"]]
    blocked = [r for r in results if r.get("blocked")]

    if fmt == "json":
        print(json.dumps(
            {
                "results": [
                    {
                        "gate": r["gate"],
                        "file": str(r["file"]),
                        "pass": r["ok"],
                        "blocked": bool(r.get("blocked")),
                        "reason": r["reason"],
                    }
                    for r in results
                ],
                "warnings": warnings,
            },
            ensure_ascii=False, indent=2,
        ))
    else:
        if not results and not warnings:
            print("no contract files found — nothing to gate")
        for w in warnings:
            print(f"\033[33mwarn\033[0m  {w}")
        for r in results:
            rel = _rel(r["file"], root)
            if r.get("blocked"):
                mark = "\033[35mblock\033[0m"
            elif r["ok"]:
                mark = "\033[32mpass\033[0m"
            else:
                mark = "\033[31mfail\033[0m"
            print(f"{mark}  [{r['gate']}] {rel}: {r['reason']}")
        if results:
            # Count by distinct contract file (a file may yield >1 finding in --all).
            files: dict = {}
            for r in results:
                files.setdefault(r["file"], []).append(r)
            passed = sum(1 for rs in files.values() if all(x["ok"] for x in rs))
            failed_files = len(files) - passed
            extra = f" ({len(failed)} findings)" if len(failed) > failed_files else ""
            blocked_note = f", {len({r['file'] for r in blocked})} blocked" if blocked else ""
            print(f"\n{passed} passed, {failed_files} failed{blocked_note} across {len(files)} contract(s){extra}")

    if blocked:
        return EXIT_BLOCKED
    return EXIT_FAIL if failed else EXIT_PASS


def _scaffold_name(gate) -> str:
    """A scaffold filename the gate's own GLOBS actually match, so `init`
    followed by `check` discovers every scaffold (and fails it loudly until
    filled — placeholders are a todo, not a pass). Before 2026-07-11 init
    wrote `example.<key>.contract.md` for all six gates while only
    data-binding's GLOBS matched `*.contract.md`: 5 of 6 scaffolds were
    invisible to `check`, teaching users a naming convention that got their
    REAL contracts silently skipped."""
    candidate = f"example.{gate.KEY}.md"
    if any(fnmatch.fnmatch(candidate, pat) for pat in gate.GLOBS):
        return candidate
    return gate.GLOBS[0].replace("*", "example", 1)


def cmd_init(path: str) -> int:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    for gate in REGISTRY:
        dest = root / _scaffold_name(gate)
        if dest.exists():
            print(f"skip (exists): {dest}")
            continue
        dest.write_text(gate.TEMPLATE, encoding="utf-8")
        print(f"wrote {dest}  ({gate.TITLE})")
    print(
        "\nnote: scaffolds contain <placeholders> and will FAIL `contract-gate check` "
        "until filled — that is the point (an unfilled contract is a todo, not a pass)."
    )
    return 0


def _read_sources(sources: list[str]) -> str:
    """Concatenate source files (spec / design / PR text) into one block, each
    under a header, capped so a giant file can't dominate the prompt."""
    chunks = []
    for s in sources:
        p = Path(s)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            chunks.append(f"### source: {s}\n[could not read: {e}]")
            continue
        if len(text) > _SOURCE_CHAR_CAP:
            text = text[:_SOURCE_CHAR_CAP] + f"\n\n[... truncated at {_SOURCE_CHAR_CAP} chars ...]"
        chunks.append(f"### source: {p.name}\n{text}")
    return "\n\n".join(chunks)


def _build_draft_prompt(gate, src_text: str) -> str:
    guidance = getattr(gate, "DRAFT_GUIDANCE", "Fill in the contract template below.")
    source_block = src_text if src_text.strip() else "[no source material provided — draft from the template and mark unknowns with `?`]"
    return (
        f"You are drafting a **{gate.TITLE}** pre-coding contract for a coding task.\n\n"
        f"{guidance}\n\n"
        f"--- CONTRACT TEMPLATE (fill this, keep the shape) ---\n\n"
        f"{gate.TEMPLATE}\n\n"
        f"--- SOURCE MATERIAL (spec / design / PR — derive the contract from this) ---\n\n"
        f"{source_block}\n"
    )


def cmd_draft(gate_key: str, sources: list[str], out: str | None, via: str | None) -> int:
    gate = GATES_BY_KEY.get(gate_key)
    if gate is None:
        print(f"fail unknown gate '{gate_key}' (available: {', '.join(GATES_BY_KEY)})", file=sys.stderr)
        return 1

    prompt = _build_draft_prompt(gate, _read_sources(sources))

    if via:
        try:
            proc = subprocess.run(shlex.split(via), input=prompt, capture_output=True, text=True)
        except (OSError, ValueError) as e:
            print(f"fail could not run --via command: {e}", file=sys.stderr)
            return 1
        if proc.returncode != 0:
            print(f"fail --via command exited {proc.returncode}: {proc.stderr.strip()}", file=sys.stderr)
            return 1
        content = proc.stdout
        dest = Path(out) if out else Path(f"{gate_key}.contract.md")
        dest.write_text(content, encoding="utf-8")
        print(f"drafted {dest} via `{via}` — review it, then `contract-gate check {dest.parent}`", file=sys.stderr)
        return 0

    if out:
        Path(out).write_text(prompt, encoding="utf-8")
        print(f"wrote draft prompt to {out} — paste it into your agent, save the reply as a .contract.md, then `contract-gate check`", file=sys.stderr)
        return 0

    # Default: emit the prompt to stdout (pipe to an agent / an LLM CLI).
    print(prompt)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="contract-gate",
        description="Pre-coding contract gate: enforce understand → contract → verify before code.",
        epilog=(
            "exit codes: 0 = all graded contracts pass (or a directory scan found "
            "nothing to gate); 1 = a contract failed, or an explicitly named file "
            "was claimed by no gate; 2 = BLOCKED (unreadable file / gate crash — "
            "the verdict is not trustworthy)."
        ),
    )
    p.add_argument("--version", action="version", version=f"contract-gate {__version__}")
    sub = p.add_subparsers(dest="cmd")

    pc = sub.add_parser(
        "check",
        help="Discover contract files under a path (or gate one explicit file) and gate them",
        description=(
            "Gate contract files. With a directory: autodiscover by each gate's GLOBS "
            "and grade every file a gate claims; files matched by GLOBS but claimed by "
            "no gate are listed as warnings (not graded, never silently invisible). "
            "With a file: grade it directly — if no gate claims it, exit 1 loudly."
        ),
        epilog="exit codes: 0 pass / 1 fail / 2 blocked (unreadable file or gate crash).",
    )
    pc.add_argument("path", nargs="?", default=".", help="Directory to scan, or one contract file (default: .)")
    pc.add_argument("--format", choices=["terminal", "json"], default="terminal")
    pc.add_argument("--all", action="store_true",
                    help="List every finding per contract (default stops at the first per file)")

    pi = sub.add_parser("init", help="Scaffold starter contract templates")
    pi.add_argument("path", nargs="?", default=".", help="Directory to write into (default: .)")

    pd = sub.add_parser(
        "draft",
        help="Emit a prompt to draft a contract from source material (spec/design/PR)",
    )
    pd.add_argument("--gate", default="data-binding", help="Which gate's contract to draft (default: data-binding)")
    pd.add_argument("--source", action="append", default=[], metavar="FILE",
                    help="Source material to derive the contract from (repeatable)")
    pd.add_argument("--out", help="Write the prompt (or, with --via, the drafted contract) to this file")
    pd.add_argument("--via", metavar="CMD",
                    help="Pipe the prompt to a local LLM CLI (e.g. \"claude -p\", \"llm\") and save its reply")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args.path, args.format, args.all)
    if args.cmd == "init":
        return cmd_init(args.path)
    if args.cmd == "draft":
        return cmd_draft(args.gate, args.source, args.out, args.via)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
