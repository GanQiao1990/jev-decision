# The gated-planner seam (`scripts/jev_policy.py`)

Shipped layer letting an external planner (LLM chat client, TypeSafe Jev
System One) influence an outer loop WITHOUT emitting domain objects,
identifiers, numerics, or verdicts. Results must not be called
"planner-guided" until a pre-registered benchmark has run on a frozen
contract.

## The whitelist chain (four deterministic gates, in order)

1. `validate_proposal(proposal, failed_gates)` — strict-JSON parse, one
   action from `ACTION_WHITELIST`, must map to a failed gate via
   `ACTION_GATES` and must not hit `ACTION_CONTRAINDICATIONS`.
   Malformed/unknown → schema rejection.
2. Copy-apply — apply the action to a **deepcopy** of the state (owned by
   the caller). No observable change → reject (`no_state_change`).
3. `preflight(state)` — caller-side deterministic feasibility check on the
   copied state; only the caller owns the domain model context.
   Infeasible/exception → reject.
4. Any rejection → rule-table fallback + `planner_proposal_rejected`
   history event; acceptance → `planner_proposal_accepted`. Jev adds a
   confidence floor and an `escalate_noul` advisory flag — never a verdict.

## Policy surface

- One shared symbolic candidate pool for every arm: rule_table, surrogate,
  llm_planner, jev, random(seed), domain-mapped.
- `random` uses a seeded `random.Random` — reproducible baselines.
- A domain-mapped baseline (e.g., a classical ranking heuristic mapped onto
  the same symbolic pool) returns `None` whenever no real mapping exists —
  recorded as a fallback. Do not invent a mapping to make the baseline look
  comparable.
- Endpoints via `summarize_policy_runs`: pass rate, mean trials-to-pass
  (successful seeds only, denominator stated), invalid/rejection rates;
  `all_seed_results` preserved verbatim — an average must not conceal an
  unfavorable seed.

## Honest-abstention taxonomy

- `None` from a request function = the failed-gate set admits no whitelist
  action (vacuous state), or the optional client is absent. Distinct from
  rejection.
- `{"jev_status": "unavailable:<exc>"}` / `request_error:<exc>` = service
  failure class, recorded verbatim — never relabelled as
  `invalid_json_proposal`.
- `"no_action"` = the official typed no-match answer; the loop converts it
  to a rule-table fallback and counts it as `jev_abstained`.

## Open audit issues observed in practice (fix before trusting numbers)

- Accepted-proposal events carrying the full preflight response bloat the
  history log; record only the small verdict scalars.
- "Trials to pass" counted via trial IDs underestimate budget when pruned
  trials skip IDs — count emitted rows instead.
- Benchmark launchers should auto-diff each arm's declared spec (including
  `feedback_policy`) — spec mismatches masquerade as contrasts otherwise.
- Any mechanism parameter set to an engineering-magnitude guess must be
  labelled an approximation until a calibrated ablation exists.

## Minimal contract for a new domain

- Replace `ACTION_WHITELIST`/`ACTION_GATES`/`ACTION_CONTRAINDICATIONS` with
  your domain's symbolic transitions (keep them symbolic — no numbers).
- Implement caller-side `apply(action, state_copy)` and
  `preflight(state_copy)`; the policy module only owns gates 1 and 4.
- Freeze `jev_snapshot.json` from `scripts/freeze_jev_snapshot.py` before
  running the jev arm; refuse to run without an accepted snapshot.
