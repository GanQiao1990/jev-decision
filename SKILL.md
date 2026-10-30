---
name: jev-decision
description: Auditable gated-planner decision machine. Let an LLM or TypeSafe Jev (System One) planner influence a closed-loop process WITHOUT emitting domain objects, parameters, scores, or verdicts — symbolic whitelist only, four deterministic gates, honest abstention, frozen service snapshots. Use when wiring an LLM into any decision loop that must stay auditable.
---

# JEV decision machine — gated planner pattern

An external planner (LLM chat client, TypeSafe Jev System One) may **pick one
symbolic transition** from a frozen whitelist. Deterministic code then
validates, applies, preflights, and records. The planner never emits
parameters, identifiers, scores, or verdicts — so nothing model-generated
reaches the evaluated system unvalidated.

## The four deterministic gates (in order)

1. **Schema + gate check** — strict-JSON parse; one action from
   `ACTION_WHITELIST`; the action must map to a *failed* gate via
   `ACTION_GATES`, and must not be contraindicated by other failures
   (`ACTION_CONTRAINDICATIONS`). Malformed/unknown → `invalid_json_proposal`;
   whitelisted-but-inapplicable → `action_not_applicable_to_failed_gates`.
2. **Apply to a copy** — apply the symbolic action to a **deepcopy** of the
   state. No observable state change → reject (`no_state_change`). This kills
   no-op proposals the schema gate cannot see.
3. **Deterministic preflight** — the *caller* (which owns the domain model)
   runs its own feasibility check on the copied state. Infeasible → reject.
4. **Fallback with an event, never silence** — every rejection falls back to
   the deterministic rule table AND writes a `planner_proposal_rejected`
   history event; acceptance writes `planner_proposal_accepted`. Rejection
   statistics are first-class evidence, not noise.

## Jev (TypeSafe System One) specifics

- Planner questions are typed: `Choice` (which action, with per-action
  criteria text) + `Noul` (should a human review this state?).
- Always include a `no_action` option: when the admissible set does not cover
  the state, abstention is the correct answer — the deterministic rule table
  takes over. Report as `jev_abstained`, never a silent pick.
- Confidence floor (`jev_min_confidence`, default 0.5); `escalate_noul` above
  threshold writes an **advisory-only** flag — it never stops the loop or
  alters a verdict.
- **Service failures are a distinct class from schema rejections**: return
  `{"jev_status": "unavailable:<exc>"}` rather than merging outages into
  `invalid_json_proposal`, or honest-refusal statistics get polluted.
- **Record the model ID the service returned**, not the one requested —
  mutable provider aliases otherwise let "asked for X" masquerade as
  "X answered".

## Freezing a mutable model service

Provider aliases are mutable; a campaign must freeze what it actually ran.
Before any benchmark, snapshot the resolved model per request, SDK version,
action-schema hash, and public inputs — store as an auditable
`jev_snapshot.json` and refuse to run the planner arm without it. The
manifest hashes cover model + policy + loop code. See
`scripts/freeze_jev_snapshot.py`.

## Decision-target ladder (choose before executing)

| Level | Object | Can support | Cannot support alone |
|---|---|---|---|
| L0 | Candidate proposed / format accepted | Search coverage, execution | Real-world utility |
| L1 | Effective state change + measurable response | Intervention represented and testable | Useful ranking |
| L2 | Paired improvement under fixed scenarios | Model- and contract-bounded gain | Deployment utility |
| L3 | Budget-matched verification utility | Fewer false positives, lower oracle cost under the declared contract | Real-world validity |
| L4 | Experimental / production result | Effect under tested conditions | Generality beyond the test |

Never promote L0–L2 to L3 because a verdict is labelled `pass` or a candidate
is historically unseen. Detail: `references/decision-objective.md`.

## Benchmark protocol

- Arms share one symbolic candidate pool: rule_table / surrogate /
  llm_planner / **jev** / random(seed) / domain-mapped baselines.
- A domain-mapped baseline must map *real* signal only; returning the
  fallback when no mapping exists is honest — inventing a mapping to look
  comparable is not.
- Endpoints: pass rate, mean trials-to-pass (denominator stated),
  invalid/rejection rates; `all_seed_results` preserved verbatim — an average
  must not conceal an unfavorable seed.
- Diff each arm's declared spec before comparing — a mismatched spec is not
  a contrast.

## Pitfalls

- Do not let the planner write numbers "for convenience" — one exception and
  the audit boundary is gone.
- Whitelist actions are *symbolic*; semantic criteria text lives beside them
  for the planner, but the validator only trusts the enum.
- Keep proposal counts as denominators in every rate; zero-proposal policies
  report 0.0, not an optimistic undefined.
- The four-gate order matters: schema → copy-apply → preflight → fallback.
  Skipping the copy-apply step lets no-ops pass.
- Accepted-proposal history events should carry only small scalars — dumping
  the whole preflight response bloats the log and hides content behind
  `default=str`.

## Reference implementation

`scripts/jev_policy.py` — dependency-free core (whitelist/gates/validation/
abstention/Jev client seam/random+LLM arms). `scripts/freeze_jev_snapshot.py`
— snapshot freezer taking the case list as an argument. Wire gates 2–3 to
your own domain model; the shipped whitelist is a generic placeholder set —
replace it with your domain's symbolic transitions.
