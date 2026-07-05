# contract-gate

**A project-agnostic pre-coding contract gate.** It enforces the discipline
**understand → contract → verify** *before* code is written — so an AI coding
agent (or a human in a hurry) can't amplify an ambiguous input into
confident-but-wrong code.

Point it at a repo; it discovers your contract files, runs every applicable
gate, and returns one verdict + exit code. Drop it into CI, a pre-commit hook,
or an agent's pre-BUILD step.

```bash
contract-gate check .        # exit 0 = all contracts sound, exit 1 = a gap
```

## Why this exists (and how it differs from the linters)

Tools like [agnix](https://github.com/agent-sh/agnix) and
[ctxlint](https://github.com/ctxlint/Ctxlint) answer *"is my config file
well-formed?"* — they lint `CLAUDE.md` / `AGENTS.md` / `SKILL.md`.

`contract-gate` answers a different question: **"did you actually understand
the problem before you started coding?"** It gates the *pre-coding contract*
(what data binds where, what the observable oracle is, which blind spots are
resolved) — the layer where migration and vibe-code bugs hide (a field wired to
the wrong source, a null that crashes the render, a spec section nobody pinned
down). No config linter checks that.

The discipline can't bake *understanding* (that's the human/agent part) — it
bakes the **guardrail**: a runnable line that says "pre-coding is sufficient →
go code", protecting against both under-prep (bugs) and over-prep (paralysis).

## Install

```bash
pipx install git+https://github.com/ducbm-amira/contract-gate   # (PyPI: planned)
# or, no install:
python3 -m contract_gate.cli check .
```

Zero runtime dependencies — the gates are Python-stdlib-only, so it runs under a
bare `python3` in any CI with no build chain.

## Quickstart

```bash
contract-gate init .          # scaffold example.<gate>.contract.md templates
$EDITOR example.data-binding.contract.md   # fill in the blind spots
contract-gate check .         # gate them
```

Or let your agent draft it from the source material, then gate the result:

```bash
contract-gate draft --gate data-binding --source spec.md --source design.html
# → emits a prompt (schema + your source + "mark unknowns with ?, don't invent")
#   paste into your agent, save the reply as *.contract.md, then:
contract-gate check .
```

`check` autodiscovers files named `*.contract.md` / `*.databinding.md` (and a
few conventional variants), runs every gate that *owns* the file (a gate skips
files it doesn't recognize — it never fails someone else's contract), and prints
a unified pass/fail with a one-line reason per contract. Exit `1` if any gate
fails, `0` otherwise. `--format json` for machine output.

## Gates

| Gate | Question it gates | Status |
|------|-------------------|--------|
| **`data-binding`** | Does every DATA element declare a source + null/empty handling? | ✅ shipped |
| **`greenfield`** | Does a design+spec task carry a 2-layer oracle (Design-ref + Observable per behavior)? | ✅ shipped |
| **`manifest`** | Does a port have a Legacy Behavior Manifest with an observable per behavior? | ✅ shipped |
| `gap-qa` | Is the gap-audit structurally complete (buckets, lenses, per-item decision)? | ⏳ planned |

## `draft` — drafting the contract (the adoption unlock)

Writing a contract by hand is the friction that kills cold-adoption. `draft`
removes it **without** adding an LLM dependency: contract-gate stays zero-dep
and agent-agnostic by acting as a **prompt-emitter**, not an LLM client. You
already work inside an agent — `draft` assembles the schema + your source
material + focused guidance into one prompt; the agent drafts, you review, the
gate verifies.

```bash
contract-gate draft --gate data-binding --source spec.md   # prompt → stdout
contract-gate draft --gate data-binding --source spec.md --via "claude -p"  # optional: pipe to a local LLM CLI, save the reply
```

The prompt is engineered so the draft **can't game the gate**: it instructs the
model to write `?` for any source it cannot derive from the material and to
never invent an endpoint/field — so real blind spots surface (the gate fails on
`?`) instead of being papered over. AI drafts the derivable 80%; the risky 20%
still lands on a human. (DP3 + DP4.)

### `data-binding` — the shipped gate

A markdown table (Screen × Element × {type; source; format; null}). Only rows
you classify (or leave unclassified) as **data** are gated:

1. every data element must declare a non-empty **source** (`ô data chưa ghi
   nguồn = chưa cho build`);
2. the map must **track null/empty handling** for data, and each data row fills
   it (a null nobody thought about is the #1 migration crash);
3. **format** is required only if you add a format column (optional to track).

Static rows (title/label/image/icon/action/state) are skipped; an unknown type
is treated as data (a false PASS defeats the gate; a false FAIL just costs a
relabel). `N/A` is a filled, considered value; `?`/`TODO`/`-` count as unfilled.
Live example: [`examples/DATA-BINDING.md`](examples/DATA-BINDING.md).

## Use in CI

```yaml
- run: pipx run contract-gate check .   # fails the job on exit 1
```

## Add a gate

A gate is one module in `contract_gate/gates/` exposing a small descriptor —
`KEY`, `TITLE`, `GLOBS`, `applies(text) -> bool`, `evaluate(text) -> (ok, reason)`,
and a `TEMPLATE` string — then one line in `gates/__init__.py::REGISTRY`. See
[`contract_gate/gates/data_binding.py`](contract_gate/gates/data_binding.py) as
the reference. Keep it stdlib-only and format-forgiving (no regex, no network).

## Design principles

- **DP1** — spec only the blind spots, not everything (over-spec = form-cứng +
  doc bloat; 80% of a screen is obvious).
- **DP2** — prefer executable checks over prose (tests self-verify).
- **DP3** — doc-time must be small + net-saving; AI drafts, human reviews.
- **DP4** — a spec is a hypothesis; pair it with a real oracle. This gate pins
  that a source is *declared*; a golden-record check verifies the wiring is
  *correct*.

Full requirement history: [`docs/TOOL-REQUIREMENTS.md`](docs/TOOL-REQUIREMENTS.md).
The `examples/` folder is one complete pre-coding pass on a real task.

## License

MIT.
