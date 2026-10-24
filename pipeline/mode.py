"""
mode.py - PUBLISH TARGET ROUTING (owner directive 2026-10-24).

Owner instruction (2026-10-24, verbatim intent): "تحلیل‌های هوش مصنوعی به کانال تست
میره... از این استفاده نکن، خودم هم حذفش می‌کنم... فقط تحلیل‌های هوش مصنوعی، نه
خبرهای ناسا" — the old private TEST channel is DELETED by the owner and must never
be used again: no mirror, no preview, nowhere. TG_TEST_CHANNEL is no longer read.

Routing model (per-channel, independent — bot verified administrator in all four):
  * fa_ai        -> TG_CH_FA_AI  Persian AI analyses       (@RazKeyhan «راز کیهان»)
  * en_ai        -> TG_CH_EN_AI  English AI analyses       (@CosmicInsightJWST)
  * fa_official  -> TG_CH_FA_OFF Persian official NASA/ESA news (@NabzeKeyhan1)
  * en_official  -> TG_CH_EN_OFF English official news     (@CosmicNewsJWST)
NASA/ESA official news goes ONLY to the *_official channels; AI analyses ONLY to
the *_ai channels — the two streams are never mixed (owner rule 2026-10-24).

A channel receives posts as soon as its secret holds a chat id/@username; setting
the secret IS the owner's go-ahead (only the owner can set repository secrets).
Kill switch: repository variable PROD_UNLOCKED="no" blocks ALL public sends
(owner brake, e.g. while on vacation); any other value incl. unset = active.
Fail-safe: missing/empty env -> that channel is silently skipped, never an error.
"""
from __future__ import annotations

import os

PUBLIC_CHANNEL_ENVS = {          # logical key -> env var carrying the chat id/@username
    "fa_ai":       "TG_CH_FA_AI",
    "en_ai":       "TG_CH_EN_AI",
    "fa_official": "TG_CH_FA_OFF",
    "en_official": "TG_CH_EN_OFF",
}


def kill_switch() -> bool:
    """True only when the owner explicitly set PROD_UNLOCKED='no' (blocks all sends)."""
    return (os.environ.get("PROD_UNLOCKED", "") or "").strip().lower() == "no"


def publish_targets() -> list[tuple[str, str, str]]:
    """[(key, chat_id, lang)] the run may publish to RIGHT NOW.
    Per-channel: every configured public channel is a target, independently.
    No test channel exists anymore (owner deleted it, directive 2026-10-24)."""
    if kill_switch():
        return []
    targets: list[tuple[str, str, str]] = []
    for key, env in PUBLIC_CHANNEL_ENVS.items():
        chat = (os.environ.get(env, "") or "").strip()
        if chat:
            targets.append((key, chat, "fa" if key.startswith("fa") else "en"))
    return targets


def status_line() -> str:
    """Human-readable mode for the run summary (NEVER includes chat ids:
    state.json is committed to the public repo)."""
    mode = "KILL-SWITCH" if kill_switch() else "LIVE"
    return f"mode={mode} targets={[k for k, _c, _l in publish_targets()]}"
