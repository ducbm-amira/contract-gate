#!/usr/bin/env python3
"""contract-gate — a project-agnostic pre-coding contract gate.

Enforces the discipline **understand → contract → verify** *before* code is
written, so vibe-coding can't amplify an ambiguous input into confident-but-
wrong code. Point it at a repo; it autodiscovers contract files, runs every
applicable gate, and returns a single verdict + exit code (0 pass / 1 fail) —
drop-in for CI, a pre-commit hook, or an agent's pre-BUILD step.

Stdlib-only, zero runtime dependencies. Each gate lives in `contract_gate/
gates/` and is registered in `gates/__init__.py::REGISTRY`.

    contract-gate check [path]        # gate all contracts under path (default .)
    contract-gate check . --format json
    contract-gate init [path]         # scaffold starter contract templates
"""
from __future__ import annotations

import argparse
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


def _discover(root: Path, globs: tuple[str, ...]) -> list[Path]:
    """All files under `root` matching any of `globs`, de-duped and sorted."""
    seen: set[Path] = set()
    for g in globs:
        for p in root.rglob(g):
            if p.is_file():
                seen.add(p)
    return sorted(seen)


def cmd_check(path: str, fmt: str) -> int:
    root = Path(path)
    if not root.exists():
        print(f"fail path not found: {path}", file=sys.stderr)
        return 1

    results: list[dict] = []
    for gate in REGISTRY:
        for f in _discover(root, gate.GLOBS):
            try:
                text = f.read_text(encoding="utf-8")
            except OSError as e:
                results.append({"gate": gate.KEY, "file": f, "ok": False, "reason": f"could not read: {e}"})
                continue
            # A gate only judges files it owns — a shared name like *.contract.md
            # that holds a different contract is skipped, not failed.
            if not gate.applies(text):
                continue
            ok, reason = gate.evaluate(text)
            results.append({"gate": gate.KEY, "file": f, "ok": ok, "reason": reason})

    return _report(results, fmt, root)


def _report(results: list[dict], fmt: str, root: Path) -> int:
    failed = [r for r in results if not r["ok"]]

    if fmt == "json":
        print(json.dumps(
            [{"gate": r["gate"], "file": str(r["file"]), "pass": r["ok"], "reason": r["reason"]} for r in results],
            ensure_ascii=False, indent=2,
        ))
    else:
        if not results:
            print("no contract files found — nothing to gate")
        for r in results:
            try:
                rel = r["file"].relative_to(root)
            except ValueError:
                rel = r["file"]
            mark = "\033[32mpass\033[0m" if r["ok"] else "\033[31mfail\033[0m"
            print(f"{mark}  [{r['gate']}] {rel}: {r['reason']}")
        if results:
            n_pass = len(results) - len(failed)
            print(f"\n{n_pass} passed, {len(failed)} failed across {len(results)} contract(s)")

    return 1 if failed else 0


def cmd_init(path: str) -> int:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    for gate in REGISTRY:
        dest = root / f"example.{gate.KEY}.contract.md"
        if dest.exists():
            print(f"skip (exists): {dest}")
            continue
        dest.write_text(gate.TEMPLATE, encoding="utf-8")
        print(f"wrote {dest}  ({gate.TITLE})")
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
    )
    p.add_argument("--version", action="version", version=f"contract-gate {__version__}")
    sub = p.add_subparsers(dest="cmd")

    pc = sub.add_parser("check", help="Discover contract files under a path and gate them")
    pc.add_argument("path", nargs="?", default=".", help="Directory to scan (default: .)")
    pc.add_argument("--format", choices=["terminal", "json"], default="terminal")

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
        return cmd_check(args.path, args.format)
    if args.cmd == "init":
        return cmd_init(args.path)
    if args.cmd == "draft":
        return cmd_draft(args.gate, args.source, args.out, args.via)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
