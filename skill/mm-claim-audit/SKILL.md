---
name: mm-claim-audit
description: >-
  Audit image captions and alt text before you ship them. Decompose visible claims,
  verify each against the image with a cheap black-box VL model (OpenRouter/Ollama),
  and block publish when planted object/attribute/count/spatial mismatches slip through.
  Use when an agent must check image↔caption consistency, supersede prose-only
  fact-check skills, or measure verification_catch_rate on a fixed eval set. Not for
  web misinformation research, deepfake forensics, or training custom VLMs.
---

# Multimodal claim audit (`mm-claim-audit`)

## When to use

- You have an **image + caption/alt text** and need to catch visible mismatches before publishing.
- A prose-only fact-check skill (jwynia@fact-check, news workflows) cannot see pixels.
- You want a **cheap black-box VL verify loop** with logged `verification_catch_rate`.

## When not to use

- Web/news misinformation pipelines needing reverse-image search or external citations.
- Deepfake / manipulation forensics (EXIF, C2PA) — different skill shape.
- White-box mech-interp or fine-tuning VLMs.

## Procedure

1. **Freeze the artifact** — image path + caption text only. Do not pass ground-truth labels or “planted error” hints to the verifier.
2. **Decompose** the caption into atomic visible claims (one object/attribute/count/spatial fact per claim). Prefer deterministic splitting; avoid rewriting claims.
3. **Verify each claim independently** against the image using a cheap VL endpoint (`nvidia/nemotron-nano-12b-v2-vl:free` default; `qwen/qwen3-vl-32b-instruct` fallback; optional `ollama run moondream`).
4. **Verdict rule** — `support` / `refute` / `uncertain`. Treat `refute` on a shipped claim as a blocking mismatch. Log `uncertain` separately — never count as a catch.
5. **Publish gate** — do not ship the caption if any visible claim is `refute`d or if negative-control cases show false refutes.
6. **Score** (eval/lab only) — run `scripts/score_planted_errors.py` against held-out `fixtures/labels.json` (never shown to the model under test).

## Independent verification (required)

Do **not** grade your own homework in the same context that wrote the caption.

- Run verification in a **fresh thread/subagent** or via `scripts/verify_claims.py` (separate API calls per claim).
- Baseline ablation: `without_skill` = text-only fact-check (no image) to mimic prose incumbents; compare to `with_skill` atomic VL verify on identical cases.
- Log paired trials to `lab_log.jsonl`; summarize with `skill_metrics.py summarize`.

## Cheap stack

- Orchestration: Cursor **Auto** only.
- Eval subjects: `nvidia/nemotron-nano-12b-v2-vl:free`, `qwen/qwen3-vl-32b-instruct`, optional `moondream` (Ollama).

## Metrics this skill should improve

| Metric | How measured |
|---|---|
| `verification_catch_rate` | `n_caught / n_planted` on frozen fixtures via `score_planted_errors.py` |
| `success_rate` | Case passes publish gate (all planted errors caught; no false refutes on true captions) |
| `success_delta_pp` | With-skill minus without-skill success rate (×100 pp in METRICS) |
| `cross_modal_consistency_rate` | Claim-level image↔text agreement (aligned with catch rate in harness) |

## Supersession

- Improves on: `jwynia/agent-skills@fact-check`, `pedrohcgs/claude-code-my-workflow@verify-claims`, `elvisun/newsjack@fact-check`
- Delta: adds **image-grounded atomic VL verification** + measured `verification_catch_rate` vs text-only prose fact-check baseline — not another external-source paragraph checker.

## Scripts

```bash
# Single case
python3 scripts/verify_claims.py --mode with_skill \
  --image fixtures/c01_blue_circle.png \
  --caption "A solid red circle on a white background." \
  --out /tmp/verify.json

# Full paired eval (append lab_log.jsonl)
python3 scripts/run_eval.py --fixtures fixtures --out-log lab_log.jsonl
```

## References

- `references/supersession.md` — incumbent limitations (read on demand).
- `evals/evals.json` — frozen with/without cases matching lab `case_id`s.
