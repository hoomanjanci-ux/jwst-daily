"""
mode.py - HARD TEST-MODE GATE (owner directive, 2026-10-22).

Owner instruction (verbatim intent): "فعلاً سیستم خودکار نشه... تو فقط هنوز باید کد
بنویسی... بعد که چیزهای مورد نیازت کامل فراهم شد، من خودم یه تأییدیه می‌دم".
=> Publishing may ONLY go to the private test channel until BOTH conditions hold:
   1) the 4 public-channel secrets are configured, AND
   2) PROD_UNLOCKED == "yes" (GitHub Actions variable / env), flipped by the owner's
      explicit go-ahead ("تأییدیه") - never by the pipeline itself.

This module is the single source of truth for the gate; run_daily consults it before
any public-channel send. Fail-safe: on ANY ambiguity -> test-only.
"""
from __future__ import annotations

import os

PUBLIC_CHANNEL_ENVS = {          # logical key -> env var carrying the chat id/@username
    "fa_ai":       "TG_CH_FA_AI",
    "en_ai":       "TG_CH_EN_AI",
    "fa_official": "TG_CH_FA_OFF",
    "en_official": "TG_CH_EN_OFF",
}


def prod_unlocked() -> bool:
    """True only when the owner's explicit go-ahead flag is set to 'yes'
    (case-insensitive; accepts GitHub variable or secret named PROD_UNLOCKED)."""
    return (os.environ.get("PROD_UNLOCKED", "") or "").strip().lower() == "yes"


def public_channels_ready() -> bool:
    """True when ALL FOUR public channel env vars carry a value."""
    return all((os.environ.get(env, "") or "").strip()
               for env in PUBLIC_CHANNEL_ENVS.values())


def publish_targets() -> list[tuple[str, str, str]]:
    """[(key, chat_id, lang)] the run may publish to RIGHT NOW.
    Test mode  -> both FA+EN go to TG_TEST_CHANNEL.
    Prod mode  -> test channel PLUS the 4 public channels (owner still watches the test one).
    Ambiguity  -> test-only (fail-safe)."""
    targets: list[tuple[str, str, str]] = []
    test = (os.environ.get("TG_TEST_CHANNEL", "") or "").strip()
    if test:
        targets += [("test_fa", test, "fa"), ("test_en", test, "en")]
    if prod_unlocked() and public_channels_ready():
        for key, env in PUBLIC_CHANNEL_ENVS.items():
            chat = (os.environ.get(env, "") or "").strip()
            targets.append((key, chat, "fa" if key.startswith("fa") else "en"))
    return targets


def status_line() -> str:
    mode = "PRODUCTION" if (prod_unlocked() and public_channels_ready()) else "TEST-ONLY"
    return (f"mode={mode} prod_unlocked={prod_unlocked()} "
            f"public_channels_ready={public_channels_ready()}")
