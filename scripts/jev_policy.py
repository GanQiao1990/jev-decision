"""Auditable feedback-policy seam for a closed-loop decision process.

This module deliberately does *not* let a language model emit domain
objects, identifiers, numerical targets, or verdicts.  A planner may only
pick one symbolic transition from :data:`ACTION_WHITELIST`; the host loop
then applies and verifies the resulting state through its own deterministic
paths.

The shipped whitelist is a GENERIC placeholder set for an iterative
search/optimization loop.  Replace ``ACTION_WHITELIST``, ``ACTION_GATES``,
``ACTION_CONTRAINDICATIONS`` and ``JEV_ACTION_CRITERIA`` with your domain's
symbolic transitions — keep them symbolic: no numbers, no identifiers.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import random
from typing import Any

log = logging.getLogger(__name__)


# The shared candidate pool for rule, surrogate, LLM, random and
# domain-mapped comparisons.  Values are symbolic by design: no
# planner-controlled numeric settings can reach the evaluated system.
ACTION_WHITELIST = frozenset({
    "widen_search",
    "narrow_search",
    "raise_budget_tier",
    "switch_strategy",
    "reduce_scope",
    "escalate_to_human",
    "relax_soft_constraint",
})

ACTION_GATES = {
    "widen_search": frozenset({"coverage_pass"}),
    "narrow_search": frozenset({"budget_pass", "resource_pass"}),
    "raise_budget_tier": frozenset({"quality_pass"}),
    "switch_strategy": frozenset({"convergence_pass"}),
    "reduce_scope": frozenset({"budget_pass"}),
    "escalate_to_human": frozenset({"safety_pass"}),
    "relax_soft_constraint": frozenset({"feasibility_pass"}),
}

# Gate failures that make an action self-defeating even when its own gate
# also failed.  Raising the budget tier while the budget gate is failing
# would worsen the exact condition the gate exists to detect.
ACTION_CONTRAINDICATIONS = {
    "raise_budget_tier": frozenset({"budget_pass"}),
    "relax_soft_constraint": frozenset({"safety_pass"}),
}


def applicable_actions(failed_gates: list[str]) -> list[str]:
    """Whitelist actions whose gate failed, minus contraindicated ones."""
    return sorted(
        action for action, gates in ACTION_GATES.items()
        if gates.intersection(failed_gates)
        and not ACTION_CONTRAINDICATIONS.get(
            action, frozenset()).intersection(failed_gates))


@dataclass(frozen=True)
class ProposalValidation:
    accepted: bool
    action: str | None
    reason: str


def parse_planner_proposal(text: str) -> dict[str, str] | None:
    """Accept one strict JSON proposal and discard all model-generated knobs."""
    try:
        raw = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("action"), str):
        return None
    proposal = {"action": raw["action"]}
    if isinstance(raw.get("rationale"), str):
        proposal["rationale"] = raw["rationale"][:500]
    return proposal


def validate_proposal(proposal: dict[str, Any] | None,
                      failed_gates: list[str]) -> ProposalValidation:
    """Validate intent before it can alter the loop state.

    This is the first deterministic gate.  Caller-side preflight is
    intentionally performed after applying a *copy* of the transition,
    because the caller alone owns the domain model context.
    """
    if not proposal or not isinstance(proposal.get("action"), str):
        return ProposalValidation(False, None, "invalid_json_proposal")
    action = proposal["action"]
    if action not in ACTION_WHITELIST:
        return ProposalValidation(False, None, "action_not_whitelisted")
    if ACTION_CONTRAINDICATIONS.get(action, frozenset()).intersection(
            failed_gates):
        return ProposalValidation(False, action,
                                  "action_contraindicated_by_failed_gates")
    if not ACTION_GATES[action].intersection(failed_gates):
        return ProposalValidation(False, action,
                                  "action_not_applicable_to_failed_gates")
    return ProposalValidation(True, action, "accepted_schema_and_gate_check")


def planner_messages(*, task: str, failed_gates: list[str],
                     available_actions: list[str]) -> list[dict[str, str]]:
    """Return the minimal public context sent to an optional LLM planner."""
    system = (
        "You select exactly one symbolic feedback action for an auditable "
        "decision loop. Do not provide identifiers, numeric settings, "
        "calculations, or verdict claims. Reply with JSON only: "
        '{"action":"one allowed action","rationale":"short reason"}.')
    payload = {"task": task, "failed_gates": failed_gates,
               "allowed_actions": available_actions}
    return [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


# Semantic descriptions of the whitelist actions, offered to a TypeSafe
# System One (Jev) planner as Choice criteria.  Jev judges WHICH symbolic
# transition fits the failed-gate profile; it still cannot emit domain
# objects, bounds, numerical values, or verdicts.
JEV_ACTION_CRITERIA = {
    "widen_search": "Widen the candidate search space (coverage gate "
                    "failing — too few distinct candidates explored).",
    "narrow_search": "Narrow the search space to cheaper regions (budget "
                     "or resource gate failing).",
    "raise_budget_tier": "Move to the next declared budget tier (quality "
                         "gate failing — more oracle budget is the only "
                         "declared lever).",
    "switch_strategy": "Switch to the next declared acquisition/search "
                       "strategy (convergence gate failing — current "
                       "strategy is stalled).",
    "reduce_scope": "Reduce the active scope to the highest-priority "
                    "subset (budget gate failing).",
    "escalate_to_human": "Escalate the state for human review (safety "
                         "gate failing — do not auto-recover).",
    "relax_soft_constraint": "Relax one declared soft constraint tier "
                             "(feasibility gate failing); hard/safety "
                             "constraints are never touched.",
    # Officially recommended no-match option: when the admissible set does
    # not cover the state (or evidence is insufficient), the correct
    # answer is abstention — the caller then falls back to the
    # deterministic rule table.  Reported as "jev_abstained", never as a
    # silent pick.
    "no_action": "No admissible action fits this state, or the evidence "
                 "is insufficient to choose; abstain so the deterministic "
                 "rule table handles it.",
}


def request_jev_proposal(client: Any | None = None, *, task: str,
                         failed_gates: list[str],
                         context: dict[str, Any] | None = None,
                         model: str = "jev-latest",
                         ) -> dict[str, Any] | None:
    """Ask a TypeSafe System One (Jev) model for one whitelisted action.

    Returns ``None`` only when the failed-gate set admits no whitelist
    action at all (a vacuous state, not a service problem).  Service
    unavailability is NOT silently merged into a schema rejection: it
    returns ``{"action": None, "jev_status": "unavailable:<exc_cls>"}`` so
    the caller can record the true failure kind — conflating a service
    outage with ``invalid_json_proposal`` would pollute honest-refusal
    statistics.
    """
    applicable = applicable_actions(failed_gates)
    if not applicable:
        return None
    try:
        from typesafe_sdk import Choice, Noul, TypeSafeClient
        if client is None:
            client = TypeSafeClient(model=model)
    except Exception as exc:
        log.warning("JEV service unavailable (%s): %s",
                    type(exc).__name__, exc)
        return {"action": None, "jev_status":
                f"unavailable:{type(exc).__name__}", "model": model}
    state: dict[str, Any] = {"task": task, "failed_gates": failed_gates}
    if context:
        state["context"] = context
    try:
        out = client.system_one(
            state=state,
            questions={
                "action": Choice(
                    instructions="Pick the single symbolic feedback action "
                                 "that best addresses the failed gates. "
                                 "Pick 'no_action' if none of the admissible "
                                 "actions fits, or the evidence is "
                                 "insufficient to choose.",
                    criteria={a: JEV_ACTION_CRITERIA[a]
                              for a in [*applicable, "no_action"]}),
                "escalate": Noul(
                    instructions="Is this failure state ambiguous or severe "
                                 "enough that a human should review it "
                                 "instead of running another automated "
                                 "round?"),
            })
    except Exception as exc:
        log.warning("JEV request failed (%s): %s", type(exc).__name__, exc)
        return {"action": None, "jev_status":
                f"request_error:{type(exc).__name__}", "model": model}
    ans = out.answers["action"]
    # Record ONLY the model id the service actually returned.  Falling
    # back to the requested model here would let "we asked for X" masquerade
    # as "X answered" — an answered-decision check requires the response
    # itself to carry the frozen model ID.
    answered_model = getattr(out, "model", None)
    out_rec = {"action": ans.choice,
               "jev_status": "ok",
               "jev": {"confidence": getattr(ans, "confidence", None),
                       "probabilities": dict(getattr(ans, "probabilities",
                                                     None) or {}),
                       "escalate_noul": out.answers["escalate"].noul}}
    if answered_model is not None:
        out_rec["model"] = answered_model
    return out_rec


def request_llm_proposal(client: Any, *, task: str,
                         failed_gates: list[str]) -> dict[str, str] | None:
    """Ask a planner through its ``chat(messages)`` interface, never required."""
    applicable = applicable_actions(failed_gates)
    if not applicable or client is None or not getattr(client, "available", True):
        return None
    try:
        out = client.chat(planner_messages(task=task,
                                           failed_gates=failed_gates,
                                           available_actions=applicable))
    except Exception as exc:  # planner unavailability is a normal degradation path
        log.warning("planner proposal request failed (%s): %s",
                    type(exc).__name__, exc)
        return None
    return parse_planner_proposal(out.get("content", "") if isinstance(out, dict) else "")


def request_random_proposal(*, failed_gates: list[str], seed: int) -> dict[str, Any] | None:
    """Uniform, seed-reproducible baseline over the shared symbolic pool."""
    applicable = applicable_actions(failed_gates)
    if not applicable:
        return None
    return {"action": random.Random(seed).choice(applicable),
            "baseline": "random", "candidate_pool": applicable}


def summarize_policy_runs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate the pre-registered comparative-policy endpoints.

    ``rows`` is preserved verbatim as ``all_seed_results`` so a mean cannot
    conceal an unfavorable seed.  Rates use proposal count as denominator;
    zero-proposal policies report 0.0 rather than an undefined optimistic rate.
    """
    n = len(rows)
    passed = sum(r.get("verdict") == "pass" for r in rows)
    pass_trials = [float(r["trials_to_pass"])
                   for r in rows if r.get("trials_to_pass") is not None]
    proposals = sum(int(r.get("proposals_total", 0)) for r in rows)
    invalid = sum(int(r.get("proposals_invalid", 0)) for r in rows)
    rejected = sum(int(r.get("proposals_rejected", 0)) for r in rows)
    return {
        "n_seeds": n,
        "pass_rate": passed / n if n else 0.0,
        "mean_trials_to_pass": (sum(pass_trials) / len(pass_trials)
                                if pass_trials else None),
        "invalid_proposal_rate": invalid / proposals if proposals else 0.0,
        "deterministic_rejection_rate": rejected / proposals if proposals else 0.0,
        "all_seed_results": rows,
    }
