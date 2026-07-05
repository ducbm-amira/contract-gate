"""Gate registry — the CLI's `check`/`init` iterate this list. Add a gate by
importing its module and appending it here; each module must expose the
descriptor surface KEY / TITLE / GLOBS / applies(text) / evaluate(text) /
TEMPLATE (see data_binding.py)."""
from . import data_binding, greenfield, manifest

REGISTRY = [data_binding, greenfield, manifest]
