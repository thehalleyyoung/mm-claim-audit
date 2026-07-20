#!/usr/bin/env python3
"""Score verifier output against held-out labels.json. Never shown to VL models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _norm(s: str) -> str:
    return s.lower().rstrip(".").strip()


def score_with_skill(result: dict, case: dict) -> dict:
    planted = [_norm(c) for c in case.get("planted_claims", [])]
    n_planted = int(case.get("n_planted", len(planted)))
    claim_rows = result.get("claims") or []
    n_refused = sum(1 for r in claim_rows if r.get("verdict") == "uncertain")

    if case.get("negative_control"):
        false_pos = sum(1 for r in claim_rows if r.get("verdict") == "refute")
        n_claims = max(1, len(claim_rows))
        return {
            "n_planted": 0,
            "n_caught": 0,
            "n_refused": n_refused,
            "verification_catch_rate": None,
            "false_positive_rate": false_pos / n_claims,
            "success_rate": 1.0 if false_pos == 0 else 0.0,
            "cross_modal_consistency_rate": 1.0 if false_pos == 0 else 0.0,
        }

    n_caught = 0
    for row in claim_rows:
        if row.get("verdict") != "refute":
            continue
        claim_norm = _norm(row.get("claim", ""))
        if planted:
            if any(p in claim_norm or claim_norm in p for p in planted):
                n_caught += 1
        else:
            n_caught += 1
    n_caught = min(n_caught, n_planted) if n_planted else 0
    # If decomposition didn't preserve planted phrasing, fall back: any refute counts toward catch
    if n_planted and n_caught == 0:
        n_refutes = sum(1 for r in claim_rows if r.get("verdict") == "refute")
        n_caught = min(n_refutes, n_planted)
    catch_rate = (n_caught / n_planted) if n_planted else None
    success = 1.0 if (n_planted and n_caught >= 1) else 0.0
    # For multi-planted: require catching at least half
    if n_planted >= 2:
        success = 1.0 if n_caught >= max(1, (n_planted + 1) // 2) else 0.0
    return {
        "n_planted": n_planted,
        "n_caught": n_caught,
        "n_refused": n_refused,
        "verification_catch_rate": catch_rate,
        "success_rate": success,
        "cross_modal_consistency_rate": catch_rate,
    }


def score_without_skill(result: dict, case: dict) -> dict:
    accurate = bool(result.get("accurate"))
    if case.get("negative_control"):
        return {
            "n_planted": 0,
            "n_caught": 0,
            "n_refused": 0,
            "verification_catch_rate": None,
            "success_rate": 1.0 if accurate else 0.0,
            "false_positive_rate": 0.0 if accurate else 1.0,
            "cross_modal_consistency_rate": 1.0 if accurate else 0.0,
        }
    n_planted = int(case.get("n_planted") or len(case.get("planted_claims") or []) or 1)
    caught = 0 if accurate else n_planted
    return {
        "n_planted": n_planted,
        "n_caught": caught,
        "n_refused": 0,
        "verification_catch_rate": caught / n_planted,
        "success_rate": 1.0 if not accurate else 0.0,
        "cross_modal_consistency_rate": caught / n_planted,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--condition", choices=["with_skill", "without_skill"], required=True)
    args = ap.parse_args()
    labels = json.loads(Path(args.labels).read_text())
    case = next(c for c in labels["cases"] if c["id"] == args.case_id)
    result = json.loads(Path(args.result).read_text())
    if args.condition == "with_skill":
        metrics = score_with_skill(result, case)
    else:
        metrics = score_without_skill(result, case)
    metrics["cost_per_trial"] = float(result.get("cost_per_trial") or 0)
    if metrics.get("n_caught"):
        metrics["cost_per_caught_failure"] = metrics["cost_per_trial"] / max(1, metrics["n_caught"])
    else:
        metrics["cost_per_caught_failure"] = None
    print(json.dumps({"case_id": args.case_id, "condition": args.condition, "metrics": metrics}))


if __name__ == "__main__":
    main()
