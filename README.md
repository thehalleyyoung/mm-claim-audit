# mm-claim-audit

Portable black-box multimodal claim audit: decompose image captions into atomic visible claims, verify each with cheap VL APIs, and measure `verification_catch_rate` vs a text-only prose fact-check baseline.

## What this is

Dual-install Claude + Cursor skill (`mm-claim-audit/`) with a frozen planted-error eval harness.
Orchestration: Cursor **Auto**. Eval subject: `nvidia/nemotron-nano-12b-v2-vl:free` (OpenRouter free tier).

## Quickstart (≤10 minutes)

```bash
export OPENROUTER_API_KEY=...
cd mm-claim-audit

# One planted-error case
python3 scripts/verify_claims.py --mode with_skill \
  --image fixtures/c01_blue_circle.png \
  --caption "A solid red circle on a white background." \
  --out /tmp/verify.json

# Score against held-out labels (never pass labels to the VL model)
python3 scripts/score_planted_errors.py \
  --labels fixtures/labels.json --case-id c01 \
  --result /tmp/verify.json --condition with_skill

# Full paired eval → append lab_log.jsonl at repo root
python3 scripts/run_eval.py --fixtures fixtures --out-log ../../lab_log.jsonl
python3 "$DERIVE_HOME/scripts/skill_metrics.py" summarize --lab-log ../../lab_log.jsonl --out-dir ../..
```

Paid fallback: `qwen/qwen3-vl-32b-instruct`. Optional local CPU: `ollama pull moondream` (first pull may exceed 10 minutes).

## Measured usefulness

See `METRICS.md` and `figures/`. Numbers come only from `lab_log.jsonl`.

| Metric | With skill | Without | Δ |
|---|---|---|---|
| `verification_catch_rate` (mean) | 0.75 | 0 | 0.75 |
| `success_rate` (mean) | 1 | 0.2 | 0.8 |
| `success_delta_pp` | — | — | 80 |
| `cross_modal_consistency_rate` (mean) | 0.8 | 0.2 | 0.6 |

- **20** paired trials (with_skill=**10**, without_skill=**10**) on frozen synthetic fixtures.
- Usefulness blend (logging): **0.8434**
- Hard cases (c07/c08 multi-claim): with_skill catch rate below single-claim cases on this cheap VL — procedure still beats text-only (**0**).

## Related work / incumbents

Not greenfield on *problem shape* — research and marketplace neighbors exist — but no `same_form` portable skill with this harness surfaced in census:

- [jwynia/agent-skills@fact-check](https://skills.sh/jwynia/agent-skills/fact-check) — prose claim extraction; no image-grounded planted-error catch-rate.
- [garrytan/gbrain@cross-modal-review](https://skills.sh/garrytan/gbrain/cross-modal-review) — cross-**model** review naming trap, not caption↔pixel audit.
- [CapMAS (arxiv:2412.15484)](https://arxiv.org/html/2412.15484v2) — atomic proposition verify in papers; not a cheap agent SKILL.md + with/without ablation.
- [PatchTrust (OpenReview)](https://openreview.net/forum?id=J5qlF049Ei) / [GAVEL](https://arxiv.org/html/2606.26923v1) — black-box caption error detection research; no shipped agent skill package.

**Supersession delta:** image-grounded atomic VL verification + automated `verification_catch_rate` vs text-only baseline mimicking prose fact-check incumbents.

## Install

```bash
bash ~/.derive/scripts/install_skill.sh mm-claim-audit --repo-root .
```

## Limitations

- Synthetic geometric fixtures only — not photo-real misinformation or OCR stress tests.
- Cheap free VL misses some multi-claim cases (see c07/c08 at 0.5 catch rate).
- Text-only baseline intentionally has **no image** — mirrors prose incumbents, not one-shot VL upper bound.
- `$0` cost trials use OpenRouter `:free` tier; rate limits apply.

## Seed

Run seed: `f725ffac4ee2ea6e6deddb9116937b5e99e1a8e7795eae9390a501a42f9d22bf` (entropy harvest 2026-07-20).
