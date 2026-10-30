#!/usr/bin/env python3
"""Freeze an auditable acceptance snapshot of the external Jev planner.

This is deliberately called a *service snapshot*, not a local checkpoint:
the provider exposes mutable request aliases.  The script records the
resolved response model for every request, the SDK version, action-schema
hash, and all public inputs/typed outputs needed to audit a campaign.

Cases are supplied as a JSON file: a list of
``{"name": <case label>, "failed_gates": [<gate>, ...]}`` records.  A
benchmark should refuse to run the jev arm unless this script exits 0 and
its snapshot file is stored with the campaign manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jev_policy import (ACTION_GATES, ACTION_WHITELIST,  # noqa: E402
                        request_jev_proposal, validate_proposal)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--states", required=True,
                    help="JSON file: [{'name': ..., 'failed_gates': [...]}]")
    ap.add_argument("--schema-file", default=None,
                    help="Optional extra file hashed into the manifest "
                         "(e.g. your verdict contract source).")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cases = json.loads(Path(args.states).read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        failed = list(case["failed_gates"])
        allowed = sorted(action for action, gates in ACTION_GATES.items()
                         if gates.intersection(failed))
        raw = request_jev_proposal(task=case["name"], failed_gates=failed,
                                   model=args.model)
        service_ok = (raw is not None
                      and raw.get("jev_status", "ok") == "ok")
        checked = validate_proposal(raw, failed)
        abstained = bool(service_ok
                         and raw.get("action") == "no_action")
        # Service failures keep their true reason (unavailable:* /
        # request_error:*); they are never relabelled as schema
        # rejections, which would corrupt the refusal statistics.
        reason = (checked.reason if service_ok or raw is None
                  else raw["jev_status"])
        # no_action is the official no-match option: a valid typed
        # response that the loop converts to a rule-table fallback.
        rows.append({"task": case["name"], "failed_gates": failed,
                     "allowed_actions": allowed, "proposal": raw,
                     "service_ok": service_ok,
                     "accepted": checked.accepted or abstained,
                     "abstained": abstained,
                     "reason": reason,
                     "action_in_candidate_pool": bool(
                         service_ok and (raw.get("action") in allowed
                                         or abstained))})

    resolved = sorted({r["proposal"].get("model") for r in rows
                       if r.get("proposal") and r["proposal"].get("model")})
    valid = sum(r["accepted"] for r in rows)
    in_pool = sum(r["action_in_candidate_pool"] for r in rows)
    n_service_fail = sum(not r["service_ok"] for r in rows)
    out = {
        "kind": "external_service_snapshot_not_local_checkpoint",
        "requested_model": args.model,
        "resolved_models": resolved,
        "typesafe_sdk_version": importlib.metadata.version("typesafe-sdk"),
        "action_whitelist": sorted(ACTION_WHITELIST),
        "action_schema_sha256": _sha256(
            Path(__file__).resolve().parent / "jev_policy.py"),
        "n_cases": len(rows),
        "n_abstained": sum(r["abstained"] for r in rows),
        "n_service_failures": n_service_fail,
        "accepted_schema_rate": valid / len(rows) if rows else 0.0,
        "action_in_candidate_pool_rate": in_pool / len(rows) if rows else 0.0,
        "low_confidence_rate": (sum(
            ((r.get("proposal") or {}).get("jev") or {}).get("confidence", 1) < 0.5
            for r in rows) / len(rows) if rows else 0.0),
        "rows": rows,
    }
    if args.schema_file:
        out["contract_sha256"] = _sha256(Path(args.schema_file))
    out["acceptance_pass"] = (
        n_service_fail == 0 and len(resolved) == 1
        and valid == len(rows) and in_pool == len(rows))
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({k: out[k] for k in (
        "requested_model", "resolved_models", "n_cases", "n_abstained",
        "n_service_failures", "accepted_schema_rate",
        "action_in_candidate_pool_rate", "low_confidence_rate",
        "acceptance_pass")}, ensure_ascii=False))
    return 0 if out["acceptance_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
