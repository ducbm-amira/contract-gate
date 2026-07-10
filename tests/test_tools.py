#!/usr/bin/env python3
"""Wire the top-level tools/ tests into the standard `unittest discover -s tests`
run so they stay counted by the suite.

The characterize family (characterize.py / characterize_manifest.py /
characterize_pdf.py) lives at top-level `tools/` — repo-path-consumed, NOT shipped
inside the `contract_gate` pip package. Their `*_test.py` files sit alongside them
and self-insert their own dir onto sys.path, so they import the module-under-test
by bare name. This thin runner discovers those `*_test.py` files via a module-level
`load_tests` hook so `python3 -m unittest discover -s tests` runs them too, without
relocating them into tests/.
"""
from __future__ import annotations

import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
TOOLS_DIR = REPO_ROOT / "tools"


def load_tests(loader, standard_tests, pattern):  # noqa: ARG001 (unittest hook signature)
    """unittest load_tests protocol: fold every tools/*_test.py into this suite."""
    tools_suite = loader.discover(
        start_dir=str(TOOLS_DIR),
        pattern="*_test.py",
        top_level_dir=str(TOOLS_DIR),
    )
    standard_tests.addTests(tools_suite)
    return standard_tests


if __name__ == "__main__":
    unittest.main()
