"""
quality.py - message/image QUALITY ASSESSMENT (کیفیت‌سنجی) module.

Two layers, both fail-safe (never block the pipeline, never raise):

  L1 HEURISTIC (always on, zero cost, offline):
     - sharpness      : Laplacian variance on downscaled grayscale (focus proxy)
     - contrast       : robust std of luminance
     - brightness     : mean luminance distance from ideal ~0.45 ( clipping penalty)
     - dynamic range  : p99-p1 spread of luminance
     - roi_prominence : already computed by annotator (passed in by caller)
     -> composite 0-100 weighted sum (weights below, tuned on real JWST renders)

  L2 AI (plugs in the moment the owner supplies a free OpenAI-compatible API):
     env:  QAI_BASE_URL (e.g. https://xxx/v1)  QAI_API_KEY  QAI_MODEL (default gpt-4o-mini)
           QAI_VISION_MODEL (optional; image scoring)  QAI_MIN_SCORE (default 0)
     - ai_score_message(): scores the FA/EN caption + analysis payload (text chat)
     - ai_score_image():   vision scoring of the rendered PNG (base64 data URL)
     -> returns {"score": 0-100, "clarity":.., "accuracy":.., "appeal":.., "notes":..}
        or None when no API configured / any failure (timeouts, quota, bad JSON).
     One retry, 45s timeout, response_format json_object when accepted, lenient parse.

Publication policy (test phase): quality is RECORDED only; QAI_MIN_SCORE filter
activates automatically the day the owner sets it (default 0 = everything passes).
"""
from __future__ import annotations

import base64
import json
import os

import numpy as np
import requests
from PIL import Image

# L1 weights (sum = 1.0)
W_SHARP, W_CONTRAST, W_BRIGHT, W_RANGE, W_ROI = 0.35, 0.20, 0.15, 0.15, 0.15


# ---------------------------------------------------------------- L1 heuristic
def heuristic_scores(img8: np.ndarray, roi_score: float | None = None) -> dict:
    """img8: 2-D uint8 grayscale of the rendered PNG. Returns component + composite."""
    g = img8.astype(np.float32) / 255.0
    small = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((256, 256))).astype(np.float32) / 255.0
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    lap = np.abs(np.sum(
        np.stack([np.roll(np.roll(small, i, 0), j, 1) * w
                  for (i, j), w in zip([(0, 1), (0, -1), (1, 0), (-1, 0)], (1, 1, 1, 1))
                  ] + [small * -4], axis=0), axis=0))
    sharp = float(np.clip(lap.var() * 4000.0, 0, 1))          # focus proxy
    contrast = float(np.clip(g.std() / 0.25, 0, 1))            # ideal std ~0.25
    bright = float(np.clip(1.0 - abs(g.mean() - 0.45) / 0.45, 0, 1))
    p1, p99 = np.percentile(g, 1), np.percentile(g, 99)
    rng = float(np.clip((p99 - p1) / 0.85, 0, 1))
    roi = float(np.clip((roi_score or 0) / 100.0, 0, 1))
    composite = 100.0 * (W_SHARP * sharp + W_CONTRAST * contrast + W_BRIGHT * bright
                         + W_RANGE * rng + W_ROI * roi)
    return {"sharp": round(sharp, 4), "contrast": round(contrast, 4),
            "brightness": round(bright, 4), "range": round(rng, 4),
            "roi": round(roi, 4), "score": round(composite, 2)}


# ---------------------------------------------------------------- L2 AI layer
def qai_available() -> bool:
    return bool((os.environ.get("QAI_BASE_URL", "") or "").strip()
                and (os.environ.get("QAI_API_KEY", "") or "").strip())


def _chat(base, key, model, messages, vision=False, timeout=45):
    url = base.rstrip("/") + "/chat/completions"
    body = {"model": model, "messages": messages, "temperature": 0.2,
            "max_tokens": 400}
    if not vision:  # json mode is text-only safe; some vision endpoints reject it
        body["response_format"] = {"type": "json_object"}
    r = requests.post(url, json=body,
                      headers={"Authorization": f"Bearer {key}"},
                      timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse_json(content):
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:  # noqa: BLE001 - lenient: grab first {...} block
        s, e = content.find("{"), content.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(content[s:e + 1])
            except Exception:  # noqa: BLE001
                return None
    return None


SCORE_PROMPT = (
    "You are a strict Telegram astronomy-channel editor. Rate this post draft "
    "(caption + data payload) for a Persian/English JWST channel. "
    'Reply ONLY with JSON: {"score":0-100,"clarity":0-100,"accuracy":0-100,'
    '"appeal":0-100,"notes":"<=25 words"}. Score is the weighted overall quality '
    "for a non-expert audience; penalize jargon, dryness, wrong/missing facts.")
VISION_PROMPT = (
    "You are a strict photo editor for an astronomy channel. Rate this JWST render's "
    "visual quality (composition, contrast, noise, wow-factor for laypeople). "
    'Reply ONLY with JSON: {"score":0-100,"clarity":0-100,"accuracy":null,'
    '"appeal":0-100,"notes":"<=20 words"}.')


def ai_score_message(caption: str, payload: dict) -> dict | None:
    """L2 text scoring of the actual post content. None unless API configured/healthy."""
    if not qai_available():
        return None
    base = os.environ["QAI_BASE_URL"].strip()
    key = os.environ["QAI_API_KEY"].strip()
    model = (os.environ.get("QAI_MODEL", "") or "gpt-4o-mini").strip()
    msgs = [{"role": "user", "content": SCORE_PROMPT +
             f"\n\nCAPTION:\n{caption[:1200]}\n\nDATA PAYLOAD:\n"
             + json.dumps(payload, ensure_ascii=False)[:1500]}]
    for attempt in (1, 2):
        try:
            return _parse_json(_chat(base, key, model, msgs))
        except Exception:  # noqa: BLE001
            if attempt == 2:
                return None
    return None


def ai_score_image(png_path) -> dict | None:
    """L2 vision scoring of the rendered PNG. Skips silently when not configured
    or when QAI_VISION_MODEL is absent (text-only free tiers are common)."""
    vmodel = (os.environ.get("QAI_VISION_MODEL", "") or "").strip()
    if not (qai_available() and vmodel and png_path and str(png_path).endswith((".png", ".jpg", ".jpeg"))):
        return None
    try:
        b64 = base64.b64encode(open(png_path, "rb").read()).decode()
        url = ("data:image/png;base64," + b64) if str(png_path).endswith(".png") \
            else ("data:image/jpeg;base64," + b64)
        base = os.environ["QAI_BASE_URL"].strip()
        key = os.environ["QAI_API_KEY"].strip()
        msgs = [{"role": "user", "content": [
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": url}}]}]
        return _parse_json(_chat(base, key, vmodel, msgs, vision=True, timeout=60))
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- integration
def full_report(img8: np.ndarray, roi_score: float, caption: str, payload: dict,
                raw_png=None) -> dict:
    """Everything the ledger stores about one candidate post's quality.
    AI parts degrade to None when no API is configured (test phase today)."""
    rep = {"heuristic": heuristic_scores(img8, roi_score), "ai_message": None,
           "ai_image": None, "min_score_gate": float(os.environ.get("QAI_MIN_SCORE", "0"))}
    if qai_available():
        rep["ai_message"] = ai_score_message(caption, payload)
        rep["ai_image"] = ai_score_image(raw_png)
    return rep


def passes_gate(quality: dict) -> bool:
    """QAI_MIN_SCORE filter - inactive (always True) until the owner sets a threshold."""
    try:
        gate = float(os.environ.get("QAI_MIN_SCORE", "0") or 0)
    except ValueError:
        return True
    if gate <= 0:
        return True
    ai = quality.get("ai_message") or {}
    h = quality.get("heuristic") or {}
    best = max(float(ai.get("score") or 0), float(h.get("score") or 0))
    return best >= gate
