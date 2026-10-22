"""
telegram_publish.py - Telegram Bot API publisher with per-channel dedup hooks, 429 handling,
exponential backoff + jitter, and 1024-char caption / 4096-char message chunking.
NOT executed in the research sandbox (no bot token here by design; token lives in GitHub Secrets).
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"
CAPTION_LIMIT = 1024   # sendPhoto/sendDocument caption hard limit (official Bot API)
TEXT_LIMIT = 4096      # sendMessage hard limit


def _post(token, method, **payload):
    files = None
    if "photo_path" in payload:
        files = {"photo": open(payload.pop("photo_path"), "rb")}
    if "document_path" in payload:
        files = {"document": open(payload.pop("document_path"), "rb")}
    try:
        r = requests.post(API.format(token=token, method=method), data=payload,
                          files=files, timeout=60)
    finally:
        if files:
            for f in files.values():
                f.close()
    return r


def send_photo(token, chat_id, png_path, caption, parse_mode="HTML", max_retry=5):
    """Upload a PNG (<10 MB, official limit) with caption <=1024 chars. 429-aware."""
    if len(caption) > CAPTION_LIMIT:
        caption = caption[:CAPTION_LIMIT - 1] + "\u2026"
    wait = 2.0
    for attempt in range(max_retry):
        resp = _post(token, "sendPhoto", chat_id=chat_id, photo_path=str(png_path),
                     caption=caption, parse_mode=parse_mode)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:  # rate limited: obey retry_after, then retry
            time.sleep(int(resp.json().get("parameters", {}).get("retry_after", 5)) + 1)
            continue
        if resp.status_code >= 500:  # transient server error: exp backoff + jitter
            time.sleep(wait + random.uniform(0, 1))
            wait = min(wait * 2, 60)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"sendPhoto failed after {max_retry} attempts: {resp.status_code} {resp.text[:200]}")


def send_album(token, chat_id, image_paths, caption, parse_mode="HTML", max_retry=5):
    """One album post via sendMediaGroup (up to 10 photos, caption on the first).
    Used for the 4-image publication: FITS raw + FITS annotated + official JPEG raw
    + official JPEG annotated. 429/5xx aware with backoff, like send_photo."""
    if len(caption) > CAPTION_LIMIT:
        caption = caption[:CAPTION_LIMIT - 1] + "\u2026"
    files, media = {}, []
    try:
        for i, p in enumerate(image_paths[:10]):
            key = f"file{i}"
            files[key] = open(p, "rb")
            item = {"type": "photo", "media": f"attach://{key}"}
            if i == 0 and caption:
                item["caption"] = caption
                item["parse_mode"] = parse_mode
            media.append(item)
        wait = 2.0
        resp = None
        for attempt in range(max_retry):
            for f in files.values():
                f.seek(0)
            resp = requests.post(API.format(token=token, method="sendMediaGroup"),
                                 data={"media": json.dumps(media)}, files=files, timeout=120)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                time.sleep(int(resp.json().get("parameters", {}).get("retry_after", 5)) + 1)
                continue
            if resp.status_code >= 500:
                time.sleep(wait + random.uniform(0, 1))
                wait = min(wait * 2, 60)
                continue
            resp.raise_for_status()
        raise RuntimeError(f"sendMediaGroup failed after {max_retry} attempts: "
                           f"{resp.status_code if resp is not None else '?'} "
                           f"{(resp.text[:200] if resp is not None else '')}")
    finally:
        for f in files.values():
            f.close()


def send_message(token, chat_id, text, parse_mode="HTML"):
    """Long analysis text -> chunked messages (4096 chars each)."""
    chunks = [text[i:i + TEXT_LIMIT] for i in range(0, len(text), TEXT_LIMIT)] or [""]
    results = []
    for chunk in chunks:
        wait = 2.0
        for attempt in range(5):
            resp = _post(token, "sendMessage", chat_id=chat_id, text=chunk, parse_mode=parse_mode)
            if resp.status_code == 200:
                results.append(resp.json())
                break
            if resp.status_code == 429:
                time.sleep(int(resp.json().get("parameters", {}).get("retry_after", 5)) + 1)
                continue
            if resp.status_code >= 500:
                time.sleep(wait + random.uniform(0, 1))
                wait = min(wait * 2, 60)
                continue
            resp.raise_for_status()
    return results


CHANNELS = {  # placeholder targets - real chat IDs come from GitHub Secrets by the owner
    "fa_ai": "TG_CH_FA_AI", "en_ai": "TG_CH_EN_AI",
    "fa_official": "TG_CH_FA_OFF", "en_official": "TG_CH_EN_OFF",
}


def resolve_chat(env_name):
    """Read the real chat id from the environment (GitHub Secrets are injected as env vars).
    Returns empty string when not configured -> caller skips that channel safely."""
    return (os.environ.get(env_name, "") or "").strip()


def publish_to_all(token, png_path, caption_fa, caption_en, analysis_fa, analysis_en,
                   already_sent=None):
    """Fan-out to the 4 channels; per-channel state kept by the caller (dedup).
    already_sent: set of channel keys already published for this product.
    Channels whose env var is empty/missing are skipped (safe partial rollout)."""
    already_sent = already_sent or set()
    report = {}
    for key, env_name in CHANNELS.items():
        if key in already_sent:
            report[key] = "skipped (already sent)"
            continue
        chat_id = resolve_chat(env_name)
        if not chat_id:
            report[key] = "skipped (chat id not configured)"
            continue
        cap, txt = (caption_fa, analysis_fa) if key.startswith("fa") else (caption_en, analysis_en)
        send_photo(token, chat_id, png_path, cap)
        if txt:
            send_message(token, chat_id, txt)
        report[key] = "sent"
    return report
