# contract-gate

Pre-coding **contract gates** that fight vibe-code bugs by enforcing the
discipline **understand → contract (bịt chỗ mù) → verify** *before* code is
written. Each gate is a tiny, stdlib-only Python CLI with a hard verdict
(`pass`/`fail`, exit `0`/`1`) — designed to bolt into the `pinrich-cycle`
lifecycle as a runnable block, not an advisory checklist that gets skipped when
rushed.

Background & rationale: vibe-coding amplifies ambiguous input into confident,
wrong code. A gate can't bake *understanding* (the human part) — it can only
force the **process + guardrail**: mark the line "pre-coding is sufficient → go
code", guarding against both under-prep (bugs) and over-prep (paralysis).

## Why standalone (and how it relates to port-harness)

The pre-existing gates that already ship inside `pinrich-cycle` —
`manifest_gate`, `greenfield_gate`, `coverage_gate`, `characterize*` — live in
`port-harness/` (synced via the `my-claude-skill` repo) and stay there. This
repo is the **canonical home for the NEW delta gates** the contract-gate work
adds on top (see the build plan). Each new gate is authored and tested here,
then a deployed copy is dropped into `port-harness/` so the wired cycle and the
cross-machine sync keep working. Same design language as the siblings on
purpose: stdlib-only, format-forgiving pipe-table parser, no regex / no network,
`pass`/`fail` + exit `0`/`1`.

## Gates

| # | Gate | Requirement | Status |
|---|------|-------------|--------|
| **4** | **`gates/data_binding_gate.py`** — Screen × Element data-binding map + gate | R4 | ✅ built + tested (22 cases) |
| 2 | GAP-QA structure validator | R2 | ⏳ next |
| 1 / 3 / 5 / 6 | task-type detector · 7-lens gate · golden-record harness · spec-table→test-gen | R1/R3/R5 | deferred (see docs) |

Priority order and the "already-have vs delta" map are in
[`docs/TOOL-REQUIREMENTS.md`](docs/TOOL-REQUIREMENTS.md). Build #4 + #2 first
(highest value, medium effort); defer #5/#6.

## #4 — data-binding gate

Closes the layer `manifest_gate` (port oracle) and `greenfield_gate` (2-layer
design+spec oracle) both miss: the **data-binding layer** (R4). Every UI element
that shows DATA must declare **where the data comes from** and **how null/empty
is handled** — *before* build. That's exactly where UI/migration bugs hide (a
`sale_` field wired to the wrong column; a LAND record whose price is null
crashing the render; a half-ported 0-usage field). qa-verify and
design-fidelity are both blind to a wrong-source binding: the screen renders
*something*, just the wrong thing.

**Input** — a markdown table (Screen × Element × {type; source; format; null}).
A table qualifies when its header has both a **type/kind** column and a
**source/nguồn** column. Multiple per-screen tables are all evaluated; an
optional `<!-- data-binding:start --> … <!-- data-binding:end -->` delimiter
restricts the scan.

**The gate** (only the 3 highest-value rules — nothing more, per DP1):

1. every **data**-typed element must declare a non-empty **source** (R4's
   literal gate: *ô data chưa ghi nguồn = chưa cho build*);
2. the map **must track null/empty handling** for data, and each data row fills
   it (LAND-null is the #1 migration bug);
3. **format** is required only if you added a format column (optional to track).

Static rows (title/label/image/icon/action/state) are skipped. An **unknown
type is treated as data** — a false PASS defeats the gate; a false FAIL only
costs a relabel.

`N/A` is a filled, considered value (not a placeholder); `?`/`TODO`/`TBD`/`-`
count as unfilled.

### Run

```bash
python3 gates/data_binding_gate.py --map <path/to/data-binding.md>
# or, resolving <repo>/.port/<task>.databinding.md:
python3 gates/data_binding_gate.py --repo <target-repo> --task <task>
```

`pass <summary>` + exit 0, or `fail <one-line reason naming the element>` +
exit 1. A live example map is
[`examples/DATA-BINDING.md`](examples/DATA-BINDING.md) (the 売却活動報告書
sandbox, passes green).

### Test

```bash
python3 -m unittest gates/data_binding_gate_test.py -v
```

## Design principles (constraints — fight SDD's own trap)

- **DP1** — spec only the blind spots, not everything (80% of a screen is
  obvious; over-spec = form-cứng + doc bloat).
- **DP2** — prefer executable (tests) over prose (tests self-check).
- **DP3** — doc-time must be small + net-saving; AI drafts, human reviews.
- **DP4** — a spec is a hypothesis; always pair it with a real oracle (golden
  record / test / browser). This gate pins that a source is *declared*; the
  golden-record harness (#5) later verifies the wiring is *correct*.

## Examples

The `examples/` folder is one full pre-coding pass on a greenfield task
(売却活動報告書): `SPEC.md`, `design.html` (the interactive prototype = design
oracle), `GAP-QA.md` (the gap-audit output #2 will validate), and
`DATA-BINDING.md` (the R4 map #4 gates).
