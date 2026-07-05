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
import sys
from pathlib import Path

from . import __version__
from .gates import REGISTRY


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

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args.path, args.format)
    if args.cmd == "init":
        return cmd_init(args.path)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
