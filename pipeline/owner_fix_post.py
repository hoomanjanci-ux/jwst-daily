"""
owner_fix_post.py - owner-visible one-shot (2026-10-23): the FA AI news rewrite of
the Von Braun symposium item contained a glitched token (人間の) before the script
glitch guard existed. This edits THAT single message (bot's own post) to the
corrected text. Everything else stays untouched.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clear_and_hello import call  # noqa: E402

FIX_TEXT = (
    "📰 <b>ناسا از رسانه‌ها برای شرکت در سمپوزیوم ۲۰۲۶ وُن براون دعوت کرد</b>\n"
    "\n"
    "ناسا از رسانه‌ها دعوت کرده تا در سمپوزیوم کاوش فضایی وُن براون، ۲۶ تا ۲۸ اکتبر، "
    "در دانشگاه آلاباما در هانتسویل شرکت کنند. محورهای امسال این سمپوزیوم بازگشت به ماه، "
    "زیرساخت پایدار ماه، پیشرانش پیشرفتهٔ فضایی و نیروی کار فضاییِ در حال تحول است.\n"
    "\n"
    "📡 منبع: ناسا · 📅 2026-10-22\n"
    "🔗 <a href=\"https://www.nasa.gov/news-release/nasa-invites-media-to-2026-"
    "von-braun-space-exploration-symposium/\">متن کامل خبر</a>\n"
    "\n"
    "🏷 نوع: خبر رسمی — نه تحلیل هوش مصنوعی\n"
    "\n"
    "———\n"
    "🛰 <b><a href=\"https://t.me/NabzeKeyhan1\">نبض کیهان</a></b> | تپش قلب کیهان\n"
    "🔭 <a href=\"https://t.me/RazKeyhan\">تحلیل هوش مصنوعی: راز کیهان</a> ✨"
)

FIXES = {  # env of chat -> list of (message_id, text)
    "TG_CH_FA_OFF": [{"message_id": 7, "text": FIX_TEXT}],
}


def main():
    token = (os.environ.get("TG_BOT_TOKEN") or "").strip()
    confirm_in = (os.environ.get("INPUT_CONFIRM") or "").strip().upper()
    confirm_env = (os.environ.get("OWNER_CONFIRM") or "").strip()
    if not token:
        print("ABORT: TG_BOT_TOKEN missing")
        sys.exit(1)
    if confirm_in != "YES" or confirm_env != "OWNER_ORDERED_2026-10-23":
        print(f"ABORT: confirmation rails not satisfied (input={confirm_in!r})")
        sys.exit(1)

    report = {}
    for env, edits in FIXES.items():
        chat = (os.environ.get(env) or "").strip()
        for e in edits:
            code, r = call(token, "editMessageText", chat_id=chat,
                           message_id=e["message_id"], text=e["text"],
                           parse_mode="HTML", disable_web_page_preview=True)
            ok = code == 200 and r.get("ok")
            report[f"{env}#{e['message_id']}"] = {
                "ok": ok,
                "err": None if ok else str(r.get("description", r))[:160]}
            print(f"{env}#{e['message_id']}", json.dumps(report[f"{env}#{e['message_id']}"],
                                                        ensure_ascii=False))
            time.sleep(0.6)

    print("TG_FIX_POST_SUMMARY:", "ALL_OK" if all(v["ok"] for v in report.values())
          else "FAIL: " + json.dumps(report, ensure_ascii=False))
    if not all(v["ok"] for v in report.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
