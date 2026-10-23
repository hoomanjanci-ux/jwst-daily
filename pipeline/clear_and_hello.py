"""
clear_and_hello.py - owner-ordered ONE-SHOT (chat approval 2026-10-23):
  1) wipe ALL existing messages in the 4 public channels (full history clear);
  2) post ONE welcome "hello" message per channel.

After this the owner writes her/his own intro messages under the hello, then
gives the go-ahead for the rest of the setup. Never enables any scheduler
(red line #1), never touches titles/avatars/descriptions, never touches the
private test channel. The bot token is read from env and NEVER printed.

Double confirmation rails:
  * workflow_dispatch input must be exactly "YES";
  * env HELLO_CONFIRM must match the owner-order stamp.
Bot API facts used:
  * an admin with can_delete_messages can delete ANY channel post, of any age;
  * there is no "list messages" method -> brute-force deleteMessage(1..N),
    stopping after a long run of consecutive misses;
  * HTTP 429 -> sleep retry_after and retry the same id.
"""
from __future__ import annotations

import json
import os
import time

import requests

API = "https://api.telegram.org/bot{token}/{method}"
ORDER_STAMP = "OWNER_ORDERED_2026-10-23"

HELLOS = {
    "fa_news": (
        "🌌 <b>سلام کهکشان!</b>\n"
        "\n"
        "اینجا «نبض کیهان» تازه جان گرفته است — 🛰\n"
        "خانهٔ خبرهای درست فضا: ناسا، تلسکوپ جیمز وب و زیبایی‌های هستی.\n"
        "\n"
        "📰 دقیق و با منبع؛ بدون اغراق، بدون کلیک‌بیت\n"
        "🖼 تصاویر شگفت‌انگیز، با تاریخ و منبع روشن\n"
        "\n"
        "✨ به‌زودی سفر آغاز می‌شود…\n"
        "\n"
        "———\n"
        "🛰 <b>نبض کیهان</b> | تپش قلب کیهان"
    ),
    "fa_ai": (
        "🤖 <b>سلام از رازهای کیهان!</b>\n"
        "\n"
        "اینجا «راز کیهان» است — 🔭\n"
        "جایی که هوش مصنوعی داده‌ها و تصاویر جیمز وب را کنکاش می‌کند.\n"
        "\n"
        "🔬 تحلیل شفاف: واقعیت، تفسیر و عدم‌قطعیت، هر کدام جدا و روشن\n"
        "🌌 هر تصویر، رازی تازه برای کشف‌کردن\n"
        "\n"
        "✨ به‌زودی نخستین رازها گشوده می‌شوند…\n"
        "\n"
        "———\n"
        "🤖 <b>راز کیهان</b> | رازهای هستی، یک به یک"
    ),
    "en_news": (
        "🌌 <b>Hello, cosmos!</b>\n"
        "\n"
        "COSMIC NEWS just came alive — 🛰\n"
        "Your home for verified space news: NASA, JWST and the wonders of the universe.\n"
        "\n"
        "📰 Accurate &amp; sourced — no hype, no clickbait\n"
        "🖼 Breathtaking images, clearly dated and referenced\n"
        "\n"
        "✨ The journey begins soon…\n"
        "\n"
        "———\n"
        "🛰 <b>COSMIC NEWS</b> | Verified, sourced, awe-inspiring"
    ),
    "en_ai": (
        "🤖 <b>Hello from the stars!</b>\n"
        "\n"
        "This is COSMIC INSIGHT — 🔭\n"
        "Where AI-assisted analysis explores JWST data and imagery.\n"
        "\n"
        "🔬 Transparent: evidence, interpretation and uncertainty — clearly separated\n"
        "🌌 Every image hides a mystery worth exploring\n"
        "\n"
        "✨ First insights are coming soon…\n"
        "\n"
        "———\n"
        "🤖 <b>COSMIC INSIGHT</b> | See deeper, understand more"
    ),
}

CHANNELS = [  # key -> env secret holding the chat id
    ("fa_news", "TG_CH_FA_OFF", "نبض کیهان @NabzeKeyhan1"),
    ("fa_ai",   "TG_CH_FA_AI",  "راز کیهان @RazKeyhan"),
    ("en_news", "TG_CH_EN_OFF", "COSMIC NEWS @CosmicNewsJWST"),
    ("en_ai",   "TG_CH_EN_AI",  "COSMIC INSIGHT @CosmicInsightJWST"),
]

MISS_STREAK_STOP = 130   # stop scanning after this many consecutive missing ids
HARD_CAP = 3000          # absolute safety cap per channel
PACE = 0.04              # ~25 req/s worst case, well under Telegram limits


def call(token: str, method: str, **payload):
    r = requests.post(API.format(token=token, method=method),
                      data={k: str(v) for k, v in payload.items()}, timeout=60)
    try:
        code, data = r.status_code, r.json()
    except Exception:  # noqa: BLE001
        code, data = r.status_code, {"ok": False, "description": r.text[:200]}
    if code == 429:  # honour Telegram flood control
        delay = float(data.get("parameters", {}).get("retry_after", 5))
        time.sleep(min(delay + 0.5, 35))
        return call(token, method, **payload)
    return code, data


def bot_admin_rights(token: str, chat_id: str, bot_id: int) -> dict:
    _, m = call(token, "getChatMember", chat_id=chat_id, user_id=bot_id)
    res = m.get("result", {}) if m.get("ok") else {}
    return {"status": res.get("status"),
            "can_delete": bool(res.get("can_delete_messages"))}


def wipe_history(token: str, chat_id: str) -> dict:
    deleted, blocked, misses, last_hit = 0, 0, 0, 0
    stopped_at, hard = None, False
    mid = 1
    while mid <= HARD_CAP:
        code, d = call(token, "deleteMessage", chat_id=chat_id, message_id=mid)
        desc = str(d.get("description", ""))
        if code == 200 and d.get("ok"):
            deleted += 1
            last_hit, misses = mid, 0
        elif "not found" in desc or "MESSAGE_ID_INVALID" in desc or "message identifier" in desc:
            misses += 1
            if misses >= MISS_STREAK_STOP:
                stopped_at = mid
                break
        elif code == 400 and ("can't be deleted" in desc or "delete" in desc.lower()):
            blocked += 1  # exists but undeletable (rare service message)
            last_hit, misses = mid, 0
        elif "administrator" in desc or "CHATACTION" in desc.upper():
            return {"deleted": deleted, "blocked": blocked,
                    "fatal": f"NO PERMISSION: {desc}", "stopped_at": mid}
        else:  # unknown 400 -> treat as miss but keep scanning
            misses += 1
            if misses >= MISS_STREAK_STOP:
                stopped_at = mid
                break
        if mid >= HARD_CAP:
            hard = True
        mid += 1
        time.sleep(PACE)
    out = {"deleted": deleted, "blocked": blocked, "last_hit": last_hit,
           "stopped_at": stopped_at or mid, "fatal": None}
    if hard:
        out["warn"] = "hard cap reached"
    return out


def main():
    token = (os.environ.get("TG_BOT_TOKEN") or "").strip()
    confirm_in = (os.environ.get("INPUT_CONFIRM") or "").strip().upper()
    confirm_env = (os.environ.get("HELLO_CONFIRM") or "").strip()
    if not token:
        print("ABORT: TG_BOT_TOKEN missing")
        return
    if confirm_in != "YES" or confirm_env != ORDER_STAMP:
        print(f"ABORT: confirmation rails not satisfied (input={confirm_in!r})")
        return

    _, me = call(token, "getMe")
    bot = me.get("result", {}) if me.get("ok") else {}
    bot_id = bot.get("id")
    print(f"BOT: @{bot.get('username')} (id present: {bool(bot_id)})")

    report = {}
    for key, env_name, human in CHANNELS:
        chat_id = (os.environ.get(env_name) or "").strip()
        if not chat_id:
            report[key] = {"error": f"env {env_name} missing"}
            continue
        _, ch = call(token, "getChat", chat_id=chat_id)
        info = ch.get("result", {}) if ch.get("ok") else {}
        username = info.get("username") or ""
        rights = bot_admin_rights(token, chat_id, bot_id) if bot_id else {}
        print(f"\n== {key} | {human} | chat_id={chat_id} | username=@{username}")
        print("   bot rights:", json.dumps(rights, ensure_ascii=False))
        if rights.get("status") == "administrator" and not rights.get("can_delete"):
            report[key] = {"error": "bot is admin WITHOUT can_delete_messages right",
                           "rights": rights}
            continue
        wipe = wipe_history(token, chat_id)
        print("   wipe:", json.dumps(wipe, ensure_ascii=False))
        hello = {}
        if not wipe.get("fatal"):
            time.sleep(1.0)
            code, sent = call(token, "sendMessage", chat_id=chat_id,
                              text=HELLOS[key], parse_mode="HTML",
                              disable_web_page_preview=True)
            ok = code == 200 and sent.get("ok")
            mid = sent.get("result", {}).get("message_id") if ok else None
            hello = {"sent": ok, "message_id": mid,
                     "err": None if ok else str(sent.get("description", sent))[:160]}
            print("   hello:", json.dumps(hello, ensure_ascii=False))
        report[key] = {"chat": f"@{username}" if username else chat_id,
                       "wipe": wipe, "hello": hello}
        time.sleep(1.0)

    print("\nTG_CLEAR_HELLO_BEGIN")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("TG_CLEAR_HELLO_END")
    wipe_ok = all(isinstance(v, dict) and not v.get("error") and not v.get("wipe", {}).get("fatal")
                  and v.get("hello", {}).get("sent") for v in report.values())
    print("TG_CLEAR_HELLO_SUMMARY:", "ALL_OK" if wipe_ok else "PARTIAL/FAIL - inspect report")


if __name__ == "__main__":
    main()
