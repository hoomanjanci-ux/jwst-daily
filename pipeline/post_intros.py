"""
post_intros.py - owner-ordered ONE-SHOT (chat approval 2026-10-23, TXT file):
  1) wipe ALL existing messages in the 4 public channels (incl. the bot's hellos);
  2) post the OWNER'S OWN introduction text verbatim, one per channel, exactly as
     provided in Telegram_Channel_Introductions.txt (header/separator lines in the
     file are channel markers, NOT part of the message).
Plain text (no parse_mode) so wording, emojis and dashes stay exactly as written.
After this the owner has confirmed full production unlock - but THIS script never
enables any scheduler (that is done separately via GitHub API + workflow enable).
"""
from __future__ import annotations

import json
import os
import sys
import time

from clear_and_hello import CHANNELS, call, wipe_history

OWNER_STAMP = "OWNER_ORDERED_2026-10-23"

INTROS = {  # verbatim from the owner's TXT (body only, channel markers excluded)
    "fa_news": (
        "اینجا تازه‌ترین خبرهای معتبر از فضا، ناسا، تلسکوپ جیمز وب و دنیای نجوم را "
        "دنبال می‌کنیم؛ کوتاه، دقیق و همراه با منبع.\n"
        "\n"
        "محتوای این کانال با کمک هوش مصنوعی گردآوری و نوشته می‌شود تا نبض اتفاقات "
        "کیهان همیشه در دسترس شما باشد. 🚀"
    ),
    "fa_ai": (
        "اینجا هوش مصنوعی به سراغ داده‌ها و تصاویر فضایی می‌رود؛ آن‌ها را بررسی "
        "می‌کند، تحلیل می‌کند و از رازهایی می‌گوید که شاید در نگاه اول دیده نشوند.\n"
        "\n"
        "این کانال خانهٔ تحلیل‌های AI، ایده‌های علمی و سفرهای کوتاه به فیزیک، ریاضی "
        "و شگفتی‌های جهان است. ✨"
    ),
    "en_news": (
        "Your daily pulse of space: verified news from NASA, JWST, major missions, "
        "and trusted scientific sources—clear, concise, and properly sourced.\n"
        "\n"
        "The content here is gathered and written with the help of AI, keeping you "
        "connected to what is happening across the cosmos. 🚀"
    ),
    "en_ai": (
        "Here, AI looks deeper into space data and imagery—exploring the evidence, "
        "interpreting the details, and explaining what may be hidden beyond the "
        "first glance.\n"
        "\n"
        "Expect AI-assisted analysis, scientific ideas, and short journeys through "
        "physics, mathematics, and the mysteries of the universe. ✨"
    ),
}


def main():
    token = (os.environ.get("TG_BOT_TOKEN") or "").strip()
    confirm_in = (os.environ.get("INPUT_CONFIRM") or "").strip().upper()
    confirm_env = (os.environ.get("OWNER_CONFIRM") or "").strip()
    if not token:
        print("ABORT: TG_BOT_TOKEN missing")
        sys.exit(1)
    if confirm_in != "YES" or confirm_env != OWNER_STAMP:
        print(f"ABORT: confirmation rails not satisfied (input={confirm_in!r})")
        sys.exit(1)

    _, me = call(token, "getMe")
    print(f"BOT: @{(me.get('result') or {}).get('username')}")

    report = {}
    for key, env_name, human in CHANNELS:
        chat_id = (os.environ.get(env_name) or "").strip()
        if not chat_id:
            report[key] = {"error": f"env {env_name} missing"}
            continue
        _, ch = call(token, "getChat", chat_id=chat_id)
        username = (ch.get("result") or {}).get("username") or ""
        print(f"\n== {key} | {human} | @ {username}")
        wipe = wipe_history(token, chat_id)
        print("   wipe:", json.dumps(wipe, ensure_ascii=False))
        intro = {}
        if not wipe.get("fatal"):
            time.sleep(1.0)
            code, sent = call(token, "sendMessage", chat_id=chat_id,
                              text=INTROS[key], disable_web_page_preview=True)
            ok = code == 200 and sent.get("ok")
            mid = sent.get("result", {}).get("message_id") if ok else None
            intro = {"sent": ok, "message_id": mid,
                     "err": None if ok else str(sent.get("description", sent))[:160]}
            print("   intro:", json.dumps(intro, ensure_ascii=False))
        report[key] = {"chat": f"@{username}" if username else chat_id,
                       "wipe": wipe, "intro": intro}
        time.sleep(1.0)

    print("\nTG_POST_INTROS_BEGIN")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("TG_POST_INTROS_END")
    all_ok = all(isinstance(v, dict) and not v.get("error")
                 and not v.get("wipe", {}).get("fatal")
                 and v.get("intro", {}).get("sent") for v in report.values())
    print("TG_POST_INTROS_SUMMARY:", "ALL_OK" if all_ok else "PARTIAL/FAIL - inspect report")


if __name__ == "__main__":
    main()
