"""
tg_setup.py - ONE-SHOT channel profile setup (owner-ordered, 2026-10-23).
Applies avatars + titles + descriptions to the 4 public channels the owner created
and added the bot to. Dispatch-only workflow; NEVER posts any message (red line #2).

Safety rails:
  * logs the CURRENT title/description/photo before each change (red line #4);
  * only calls setChatTitle when the title actually differs;
  * verifies every step with getChat afterwards and prints BEFORE -> AFTER;
  * never touches the private test channel; never sends messages.
Token comes from env TG_BOT_TOKEN; the token itself is never printed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"
ROOT = Path(__file__).resolve().parent.parent  # repo root
P = "telegram_setup/Profiles/{f}"

CHANNELS = [
    {"key": "fa_official", "chat_id": -1004454481879, "title": "نبض کیهان",
     "photo": P.format(f="01_FA_News.png"),
     "desc": ("🔭 تازه‌ترین خبرهای معتبر فضا: ناسا، تلسکوپ جیمز وب و آرشیوهای علمی؛ "
              "دقیق، با منبع و تاریخ روشن، بدون اغراق.\n"
              "✨ تحلیل هوش مصنوعی تصاویر: @RazKeyhan")},
    {"key": "fa_ai", "chat_id": -1004366817797, "title": "راز کیهان",
     "photo": P.format(f="02_FA_AI.png"),
     "desc": ("🤖 تحلیل هوش مصنوعی از داده‌ها و تصاویر فضایی؛ با تفکیک شفاف واقعیت، "
              "استنباط و عدم‌قطعیت، همراه با ارجاع به منابع معتبر.\n"
              "📰 اخبار رسمی: @NabzeKeyhan1")},
    {"key": "en_official", "chat_id": -1003720023852, "title": "COSMIC NEWS",
     "photo": P.format(f="03_EN_News.png"),
     "desc": ("🔭 Verified space news from NASA, JWST, MAST & trusted expert sources; "
              "clearly dated, sourced and free of hype.\n"
              "✨ AI-powered analysis: @CosmicInsightJWST")},
    {"key": "en_ai", "chat_id": -1004299039937, "title": "COSMIC INSIGHT",
     "photo": P.format(f="04_EN_AI.png"),
     "desc": ("🤖 AI-assisted analysis of space data & imagery; clearly separating "
              "evidence, interpretation and uncertainty, with reliable sources.\n"
              "📰 Official news: @CosmicNewsJWST")},
]


def call(token, method, **payload):
    files = None
    if "photo_path" in payload:
        files = {"photo": open(payload.pop("photo_path"), "rb")}
    try:
        r = requests.post(API.format(token=token, method=method),
                          data={k: str(v) for k, v in payload.items()},
                          files=files, timeout=120)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {"raw": r.text[:200]}
    finally:
        if files:
            files["photo"].close()


def chat_snapshot(token, chat_id):
    code, data = call(token, "getChat", chat_id=chat_id)
    if code == 200 and data.get("ok"):
        res = data["result"]
        return {"title": res.get("title"), "bio": res.get("description") or "",
                "has_photo": bool(res.get("photo"))}
    return {"error": f"{code} {data}"}


def main():
    token = (os.environ.get("TG_BOT_TOKEN") or "").strip()
    if not token:
        print("TG_SETUP: TG_BOT_TOKEN missing - abort (no-op)")
        return
    code, me = call(token, "getMe")
    print("TG_SETUP bot:", me.get("result", {}).get("username") if code == 200 else me)

    report = []
    for ch in CHANNELS:
        cid = ch["chat_id"]
        before = chat_snapshot(token, cid)
        print(f"\n== {ch['key']} ({cid}) ==")
        print("BEFORE:", json.dumps(before, ensure_ascii=False))

        steps = {}
        # 1) title (only when different - red line #4: no needless changes)
        if before.get("title") != ch["title"]:
            c, d = call(token, "setChatTitle", chat_id=cid, title=ch["title"])
            steps["title"] = f"{c} {d.get('description', '') if not d.get('ok') else 'ok'}"
        else:
            steps["title"] = "unchanged"
        # 2) description
        c, d = call(token, "setChatDescription", chat_id=cid, description=ch["desc"])
        steps["description"] = f"{c} {'ok' if d.get('ok') else d.get('description', d)}"
        # 3) avatar
        photo = ROOT / ch["photo"]
        if not photo.exists():
            steps["photo"] = f"MISSING FILE {photo}"
        else:
            c, d = call(token, "setChatPhoto", chat_id=cid, photo_path=str(photo))
            steps["photo"] = f"{c} {'ok' if d.get('ok') else d.get('description', d)}"
        print("STEPS:", steps)

        after = chat_snapshot(token, cid)
        print("AFTER :", json.dumps(after, ensure_ascii=False))
        # bot admin status (diagnostic only)
        if code == 200:
            c2, m = call(token, "getChatMember", chat_id=cid, user_id=me["result"]["id"])
            if c2 == 200 and m.get("ok"):
                print("BOT STATUS:", m["result"].get("status"))
        report.append({"key": ch["key"], "chat_id": cid, "before": before,
                       "steps": steps, "after": after})

    print("\nTG_SETUP_BEGIN")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("TG_SETUP_END")
    print("TG_SETUP_SUMMARY: " + json.dumps(
        {r["key"]: {k: ("ok" if "ok" in str(v) or "unchanged" in str(v) or "MISSING" not in str(v) else "FAIL")
                    for k, v in r["steps"].items()} for r in report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
