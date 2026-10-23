"""
edit_intros.py - owner-ordered (2026-10-23): append the beautiful link signature
(own channel + same-language companion, ai_message.build_footer) to the 4 intro
messages ALREADY posted by the bot. Edits the bot's OWN messages only; nothing
is deleted, nothing new is posted. Message ids come from the intros run log
(message_id=5 in each channel); overridable via MSG_ID_* envs / INTRO_MSG_ID.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ai_message  # noqa: E402
from clear_and_hello import CHANNELS, call  # noqa: E402
from post_intros import INTROS  # noqa: E402

KIND = {"fa_news": "news", "fa_ai": "ai", "en_news": "news", "en_ai": "ai"}
LANG = {"fa_news": "fa", "fa_ai": "fa", "en_news": "en", "en_ai": "en"}


def main():
    token = (os.environ.get("TG_BOT_TOKEN") or "").strip()
    confirm_in = (os.environ.get("INPUT_CONFIRM") or "").strip().upper()
    confirm_env = (os.environ.get("OWNER_CONFIRM") or "").strip()
    default_mid = (os.environ.get("INTRO_MSG_ID") or "5").strip()
    if not token:
        print("ABORT: TG_BOT_TOKEN missing")
        sys.exit(1)
    if confirm_in != "YES" or confirm_env != "OWNER_ORDERED_2026-10-23":
        print(f"ABORT: confirmation rails not satisfied (input={confirm_in!r})")
        sys.exit(1)

    report = {}
    for key, env_name, human in CHANNELS:
        chat_id = (os.environ.get(env_name) or "").strip()
        mid = (os.environ.get(f"MSG_ID_{key.upper()}") or default_mid).strip()
        new_text = INTROS[key] + "\n" + ai_message.build_footer(LANG[key], KIND[key])
        code, r = call(token, "editMessageText", chat_id=chat_id, message_id=mid,
                       text=new_text, parse_mode="HTML", disable_web_page_preview=True)
        ok = code == 200 and r.get("ok")
        report[key] = {"chat": chat_id, "message_id": mid, "len": len(new_text),
                       "ok": ok, "err": None if ok else str(r.get("description", r))[:160]}
        print(key, json.dumps(report[key], ensure_ascii=False))
        time.sleep(0.6)

    print("\nTG_EDIT_INTROS_BEGIN")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("TG_EDIT_INTROS_END")
    all_ok = all(v["ok"] for v in report.values())
    print("TG_EDIT_INTROS_SUMMARY:", "ALL_OK" if all_ok else "PARTIAL/FAIL")
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
