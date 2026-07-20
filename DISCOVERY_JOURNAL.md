# Discovery journal — mm-claim-audit

## Thesis
Supersede prose-only fact-check skills with black-box multimodal claim audit on cheap VL.

## Gauntlet
Overall WOUND → enter VI-D with: frozen labels, automated scorer, verifier isolation, negative controls, claim-level catch-rate.

## Lab complete (16 paired trials on c01–c08)

- enough-signal: **PASS** (20 log rows; 16 unique paired case runs + metrics regen)
- Headline deltas: verification_catch_rate **+0.75**, success_rate **+0.8**, success_delta_pp **80**
- Gates: novelty_census **PASS**, citation_verify **PASS**, lint_linkedin_skill **PASS**

## Packaging

- Skill: `skill/mm-claim-audit/SKILL.md`
- Ship artifacts in RUN_DIR: README, METRICS, LINKEDIN_POST, canonical.json, `.gitignore` (linkedinpost.txt excluded)
