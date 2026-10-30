# jev-decision

An auditable **gated-planner decision machine** for wiring an LLM — or the
TypeSafe Jev (System One) judgment model — into a closed-loop decision
process *without* letting it emit domain objects, parameters, scores, or
verdicts.

The planner may only pick **one symbolic transition** from a frozen
whitelist. Deterministic code validates the pick against the failed-gate
profile, applies it to a **copy** of the state, preflights feasibility, and
records an accept/reject history event. Everything else — verdicts, budgets,
model edits — stays in deterministic hands.

## Why

Language-model planners are good at reading a failure profile and naming a
reasonable *kind* of intervention, and bad at being trusted with the
intervention itself. The seam lets you harvest the first while making the
second structurally impossible:

- **Symbolic whitelist only** — the planner cannot reach the evaluated
  system with a number, identifier, or verdict.
- **Honest abstention** — `no_action` is an official typed answer; service
  outages are recorded as their own class, never as schema rejections.
- **Frozen provenance** — mutable provider aliases are snapshotted
  (resolved model ID, SDK version, schema hash) before any benchmark, and
  the jev arm refuses to run without an accepted snapshot.
- **Comparable arms** — rule table, surrogate, LLM planner, Jev, seeded
  random, and domain-mapped baselines all compete over the *same* symbolic
  pool, so "planner-guided" is a measurable claim, not a vibe.

## Layout

```
SKILL.md                              agent skill — the pattern contract
references/decision-objective.md      L0–L4 decision-target ladder + checklist
references/gated-planner-seam.md      the four-gate chain and audit pitfalls
scripts/jev_policy.py                 dependency-free reference core
scripts/freeze_jev_snapshot.py        service-snapshot freezer (cases via JSON)
tests/test_jev_policy.py              unit tests (stdlib only)
```

## Quickstart

```bash
python -m pytest tests/ -q          # run the test suite (stdlib only)
python -c "import sys; sys.path.insert(0,'scripts'); import jev_policy"
```

Using the Jev arm requires the TypeSafe SDK and a service credential:

```bash
pip install typesafe-sdk
export TYPESAFE_API_KEY=<your-key>          # never commit real keys
python scripts/freeze_jev_snapshot.py \
    --states examples/states.json \
    --model jev-latest \
    --out jev_snapshot.json
```

Without a key, `request_jev_proposal` returns
`{"jev_status": "unavailable:<exc>"}` — a recorded service failure, not a
crash and not a fake proposal.

## Wiring into your loop

1. Replace the generic `ACTION_WHITELIST` / `ACTION_GATES` /
   `ACTION_CONTRAINDICATIONS` in `scripts/jev_policy.py` with your domain's
   symbolic transitions (keep them symbolic — no numbers, no identifiers).
2. Implement caller-side `apply(action, state_copy)` and
   `preflight(state_copy)` — gates 2 and 3 belong to your domain model.
3. On rejection, fall back to your deterministic rule table and write a
   `planner_proposal_rejected` event; on acceptance write
   `planner_proposal_accepted`.
4. Freeze `jev_snapshot.json` before benchmark runs; diff each arm's
   declared spec before comparing outcomes.

## License

MIT — see [LICENSE](LICENSE).
