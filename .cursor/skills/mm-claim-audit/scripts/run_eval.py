#!/usr/bin/env python3
"""Run paired without_skill / with_skill eval on frozen fixtures; append lab_log.jsonl."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument("--out-log", type=Path, default=Path("lab_log.jsonl"))
    ap.add_argument("--model", default="nvidia/nemotron-nano-12b-v2-vl:free")
    ap.add_argument("--trials-dir", type=Path, default=Path("trials"))
    args = ap.parse_args()

    scripts = Path(__file__).resolve().parent
    labels = json.loads((args.fixtures / "labels.json").read_text())
    blind = json.loads((args.fixtures / "blind_cases.json").read_text())
    args.trials_dir.mkdir(parents=True, exist_ok=True)

    trial_id = 0
    if args.out_log.exists():
        for line in args.out_log.read_text().splitlines():
            if line.strip():
                trial_id = max(trial_id, int(json.loads(line).get("trial_id", 0)))

    rows = []
    for case in blind["cases"]:
        img = args.fixtures / case["image"]
        caption = case["caption"]
        label_case = next(c for c in labels["cases"] if c["id"] == case["id"])
        for condition in ("without_skill", "with_skill"):
            trial_id += 1
            outp = args.trials_dir / f"{case['id']}_{condition}.json"
            subprocess.check_call(
                [
                    sys.executable,
                    str(scripts / "verify_claims.py"),
                    "--mode",
                    condition,
                    "--image",
                    str(img),
                    "--caption",
                    caption,
                    "--model",
                    args.model,
                    "--out",
                    str(outp),
                ]
            )
            score = subprocess.check_output(
                [
                    sys.executable,
                    str(scripts / "score_planted_errors.py"),
                    "--labels",
                    str(args.fixtures / "labels.json"),
                    "--case-id",
                    case["id"],
                    "--result",
                    str(outp),
                    "--condition",
                    condition,
                ],
                text=True,
            )
            metrics = json.loads(score)["metrics"]
            clean = {k: v for k, v in metrics.items() if v is not None and isinstance(v, (int, float))}
            rows.append(
                {
                    "trial_id": str(trial_id),
                    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "hypothesis": "atomic VL claim verify beats text-only prose fact-check",
                    "condition": condition,
                    "model": args.model,
                    "case_id": case["id"],
                    "metrics": clean,
                    "notes": f"error_type={label_case['error_type']}; neg={label_case['negative_control']}",
                }
            )

    with args.out_log.open("a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(json.dumps({"appended": len(rows), "log": str(args.out_log)}))


if __name__ == "__main__":
    main()
