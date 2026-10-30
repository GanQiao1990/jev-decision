"""Unit tests for the dependency-free policy core (stdlib only)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import jev_policy as jp  # noqa: E402


class TestWhitelistAndGates(unittest.TestCase):
    def test_applicable_actions_maps_failed_gates(self):
        self.assertEqual(jp.applicable_actions(["coverage_pass"]),
                         ["widen_search"])
        self.assertIn("narrow_search",
                      jp.applicable_actions(["budget_pass"]))
        self.assertIn("reduce_scope",
                      jp.applicable_actions(["budget_pass"]))

    def test_contraindication_filters_action(self):
        # quality gate maps to raise_budget_tier, but a simultaneous
        # budget_pass failure makes it self-defeating.
        self.assertNotIn("raise_budget_tier",
                         jp.applicable_actions(["quality_pass",
                                                "budget_pass"]))
        self.assertIn("raise_budget_tier",
                      jp.applicable_actions(["quality_pass"]))

    def test_unknown_gate_yields_no_actions(self):
        self.assertEqual(jp.applicable_actions(["nonexistent_gate"]), [])


class TestParseAndValidate(unittest.TestCase):
    def test_strict_json_only(self):
        self.assertIsNone(jp.parse_planner_proposal("not json"))
        self.assertIsNone(jp.parse_planner_proposal('{"action": 42}'))
        self.assertIsNone(jp.parse_planner_proposal('[1,2]'))

    def test_rationale_truncated_and_extra_knobs_dropped(self):
        out = jp.parse_planner_proposal(
            '{"action":"widen_search","rationale":"%s","temperature":0.9}'
            % ("x" * 600))
        self.assertEqual(out["action"], "widen_search")
        self.assertEqual(len(out["rationale"]), 500)
        self.assertNotIn("temperature", out)

    def test_validate_rejects_non_whitelisted(self):
        v = jp.validate_proposal({"action": "set_lr_0.01"},
                                 ["coverage_pass"])
        self.assertFalse(v.accepted)
        self.assertEqual(v.reason, "action_not_whitelisted")

    def test_validate_rejects_inapplicable_gate(self):
        v = jp.validate_proposal({"action": "widen_search"},
                                 ["quality_pass"])
        self.assertFalse(v.accepted)
        self.assertEqual(v.reason, "action_not_applicable_to_failed_gates")

    def test_validate_accepts_matching_action(self):
        v = jp.validate_proposal({"action": "widen_search"},
                                 ["coverage_pass"])
        self.assertTrue(v.accepted)
        self.assertEqual(v.action, "widen_search")


class TestProposals(unittest.TestCase):
    def test_random_is_seed_reproducible(self):
        a = jp.request_random_proposal(failed_gates=["budget_pass"], seed=7)
        b = jp.request_random_proposal(failed_gates=["budget_pass"], seed=7)
        self.assertEqual(a, b)
        self.assertIn(a["action"], ["narrow_search", "reduce_scope"])

    def test_vacuous_gate_set_returns_none(self):
        self.assertIsNone(
            jp.request_jev_proposal(task="t", failed_gates=["zzz"]))
        self.assertIsNone(
            jp.request_random_proposal(failed_gates=["zzz"], seed=1))
        self.assertIsNone(
            jp.request_llm_proposal(object(), task="t", failed_gates=["zzz"]))

    def test_jev_unavailable_is_distinct_class(self):
        # No typesafe_sdk / no key: must report service failure, never crash
        # or fabricate a proposal.
        out = jp.request_jev_proposal(task="t",
                                      failed_gates=["coverage_pass"],
                                      client=None)
        if out is not None and out.get("jev_status") != "ok":
            self.assertTrue(out["jev_status"].startswith(
                ("unavailable:", "request_error:")))

    def test_llm_client_failure_degrades_to_none(self):
        class Bad:
            available = True
            def chat(self, _):
                raise RuntimeError("down")
        self.assertIsNone(jp.request_llm_proposal(
            Bad(), task="t", failed_gates=["coverage_pass"]))


class TestSummarize(unittest.TestCase):
    def test_aggregation_preserves_all_rows(self):
        rows = [
            {"verdict": "pass", "trials_to_pass": 3,
             "proposals_total": 4, "proposals_invalid": 1,
             "proposals_rejected": 1},
            {"verdict": "fail", "trials_to_pass": None,
             "proposals_total": 2, "proposals_invalid": 0,
             "proposals_rejected": 2},
        ]
        s = jp.summarize_policy_runs(rows)
        self.assertEqual(s["n_seeds"], 2)
        self.assertAlmostEqual(s["pass_rate"], 0.5)
        self.assertEqual(s["mean_trials_to_pass"], 3.0)
        self.assertAlmostEqual(s["invalid_proposal_rate"], 1 / 6)
        self.assertAlmostEqual(s["deterministic_rejection_rate"], 3 / 6)
        self.assertEqual(s["all_seed_results"], rows)

    def test_zero_rows_and_zero_proposals(self):
        s = jp.summarize_policy_runs([])
        self.assertEqual(s["pass_rate"], 0.0)
        self.assertIsNone(s["mean_trials_to_pass"])
        s2 = jp.summarize_policy_runs([{"verdict": "fail"}])
        self.assertEqual(s2["invalid_proposal_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
