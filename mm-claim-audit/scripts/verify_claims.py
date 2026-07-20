#!/usr/bin/env python3
"""Black-box multimodal claim verification (cheap OpenRouter VL).

Inputs: image path + caption (and optional atomic claims).
Calls a named VL model with image+text only — never receives planted-error labels.
Outputs structured verdicts for with_skill, or a coarse accurate flag for without_skill.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.request
from pathlib import Path

VERIFY_PROMPT = (
    "You are verifying whether a claim is visually supported by the image. "
    "Reply with ONLY one JSON object: "
    '{"verdict":"support"|"refute"|"uncertain","reason":"<short>"}. '
    "support = the claim is clearly true given the image. "
    "refute = the claim is clearly false given the image. "
    "uncertain = cannot tell from the image."
)

# without_skill mimics prose-only fact-check incumbents: no image access.
TEXT_ONLY_PROMPT = (
    "You are a text-only fact checker with NO image. "
    "Given only this caption, decide if it is factually trustworthy to publish. "
    "Without visual evidence you cannot verify visual attributes. "
    "Reply ONLY JSON: "
    '{"accurate":true|false,"issues":["..."]}. '
    "If you cannot verify visual claims without an image, set accurate=true "
    "(accept the caption) unless the text is internally contradictory."
)

# Optional secondary baseline: one-shot VL (logged as condition other if used).
ONESHOT_VL_PROMPT = (
    "Does this caption accurately describe the image? "
    "Reply ONLY JSON: "
    '{"accurate":true|false,"issues":["..."]}.'
)


def b64_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def path_is_png(p: Path) -> bool:
    return p.suffix.lower() == ".png"


def openrouter_chat(
    model: str,
    text: str,
    image_path: Path | None = None,
    timeout: int = 90,
) -> tuple[str, float]:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY required")
    if image_path is None:
        content: list | str = text
    else:
        mime = "image/png" if path_is_png(image_path) else "image/jpeg"
        content = [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64_image(image_path)}"},
            },
        ]
    body = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": content}],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/halley/mm-claim-audit",
            "X-Title": "mm-claim-audit",
        },
        method="POST",
    )
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            break
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
            # rebuild request body each retry
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(body).encode(),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/halley/mm-claim-audit",
                    "X-Title": "mm-claim-audit",
                },
                method="POST",
            )
    else:
        raise SystemExit(f"openrouter failed after retries: {last_err}")
    cost = 0.0
    usage = data.get("usage") or {}
    if "total_cost" in usage:
        cost = float(usage["total_cost"])
    elif "cost" in data:
        cost = float(data["cost"])
    msg = data["choices"][0]["message"]["content"]
    if isinstance(msg, list):
        msg = "".join(part.get("text", "") for part in msg if isinstance(part, dict))
    return str(msg), cost


def parse_json_loose(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def decompose_caption(caption: str) -> list[str]:
    """Deterministic lightweight claim split (no LLM) for reproducibility."""
    parts = []
    for chunk in caption.replace(";", ".").split("."):
        c = chunk.strip().strip(",")
        if len(c) < 8:
            continue
        if not c.endswith("."):
            c = c + "."
        parts.append(c)
    return parts or [caption.strip()]


def verify_claims(image: Path, claims: list[str], model: str) -> dict:
    results = []
    total_cost = 0.0
    for claim in claims:
        prompt = VERIFY_PROMPT + f"\n\nClaim: {claim}"
        raw, cost = openrouter_chat(model, prompt, image_path=image)
        total_cost += cost
        try:
            obj = parse_json_loose(raw)
            verdict = str(obj.get("verdict", "uncertain")).lower().strip()
            if verdict not in ("support", "refute", "uncertain"):
                verdict = "uncertain"
            reason = str(obj.get("reason", ""))[:200]
        except Exception as e:
            verdict, reason = "uncertain", f"parse_error:{e}"
        results.append({"claim": claim, "verdict": verdict, "reason": reason, "raw": raw[:300]})
    return {"claims": results, "cost_per_trial": total_cost, "model": model}


def text_only_baseline(caption: str, model: str) -> dict:
    """Prose-only incumbent baseline: no image provided."""
    prompt = TEXT_ONLY_PROMPT + f"\n\nCaption: {caption}"
    raw, cost = openrouter_chat(model, prompt, image_path=None)
    try:
        obj = parse_json_loose(raw)
        accurate = bool(obj.get("accurate"))
        issues = obj.get("issues") or []
    except Exception as e:
        accurate, issues = True, [f"parse_error:{e}"]
    return {
        "accurate": accurate,
        "issues": issues,
        "raw": raw[:500],
        "cost_per_trial": cost,
        "model": model,
        "baseline": "text_only_no_image",
    }


def oneshot_vl(image: Path, caption: str, model: str) -> dict:
    prompt = ONESHOT_VL_PROMPT + f"\n\nCaption: {caption}"
    raw, cost = openrouter_chat(model, prompt, image_path=image)
    try:
        obj = parse_json_loose(raw)
        accurate = bool(obj.get("accurate"))
        issues = obj.get("issues") or []
    except Exception as e:
        accurate, issues = True, [f"parse_error:{e}"]
    return {
        "accurate": accurate,
        "issues": issues,
        "raw": raw[:500],
        "cost_per_trial": cost,
        "model": model,
        "baseline": "oneshot_vl",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["with_skill", "without_skill"], required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--model", default="nvidia/nemotron-nano-12b-v2-vl:free")
    ap.add_argument("--claims-json", default="", help="optional JSON list; else decompose caption")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    image = Path(args.image)
    if args.mode == "without_skill":
        out = text_only_baseline(args.caption, args.model)
        out["mode"] = "without_skill"
    else:
        claims = json.loads(args.claims_json) if args.claims_json else decompose_caption(args.caption)
        out = verify_claims(image, claims, args.model)
        out["mode"] = "with_skill"
        out["decomposed_claims"] = claims
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({"wrote": args.out, "mode": out["mode"], "model": out["model"]}))


if __name__ == "__main__":
    main()
