"""
tg_discover.py - owner-authorized channel auto-discovery (debug tool, workflow_dispatch only).

Mission: the bot itself discovers chat ids of channels it was added to (private test
channel AND the 4 future public channels), so the owner never has to forward messages
or copy ids manually.

Method (official Bot API, zero cost):
  1) getUpdates  -> my_chat_member / channel_post / message updates carry the full
     chat object (id, title, username, type). Offset loop until drained.
  2) For every candidate @username found OR supplied via env TG_TRY_USERNAMES,
     call getChat to resolve public channels without any prior update.
  3) Print a TABLE of unique chats (id / title / username / type / source).
  The token itself is NEVER printed; GitHub log-masking protects it anyway.
Exit code 0 always (debug tool must not fail the workflow).
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def _call(token, method, **payload):
    try:
        r = requests.post(API.format(token=token, method=method), json=payload, timeout=30)
        data = r.json()
        if not data.get("ok"):
            return {"ok": False, "error": f"{data.get('error_code')} {data.get('description')}"}
        return data
    except Exception as e:  # noqa: BLE001 - debug tool never raises
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _chat_row(chat, source):
    return {
        "id": chat.get("id"),
        "type": chat.get("type"),
        "title": chat.get("title") or chat.get("username") or "-",
        "username": chat.get("username"),
        "source": source,
    }


def discover(token, try_usernames=()):
    """Drain getUpdates, collect every chat object, then resolve optional usernames.
    Returns (rows, notes)."""
    rows, notes = [], []
    seen = set()

    def add(chat, source):
        cid = chat.get("id")
        if cid is None or cid in seen:
            return
        seen.add(cid)
        rows.append(_chat_row(chat, source))

    offset = 0
    for _round in range(10):  # hard drain cap
        data = _call(token, "getUpdates", offset=offset, timeout=5, limit=100)
        if not data.get("ok"):
            notes.append(f"getUpdates error: {data.get('error')}")
            break
        ups = data.get("result") or []
        if not ups:
            break
        for u in ups:
            offset = max(offset, u["update_id"] + 1)
            for key in ("my_chat_member", "chat_member", "chat_join_request"):
                c = (u.get(key) or {}).get("chat")
                if c:
                    add(c, key)
            for key in ("channel_post", "edited_channel_post", "message", "edited_message"):
                c = (u.get(key) or {}).get("chat")
                if c:
                    add(c, key)
        if len(ups) < 100:
            break
        time.sleep(0.3)

    for uname in try_usernames:
        uname = (uname or "").strip()
        if not uname:
            continue
        if not uname.startswith("@"):
            uname = "@" + uname
        data = _call(token, "getChat", chat_id=uname)
        if data.get("ok"):
            add(data["result"], "getChat")
        else:
            notes.append(f"getChat({uname}): {data.get('error')}")

    for r in rows:  # enrich private channels with readable titles
        if r["id"] and str(r["id"]).startswith("-100"):
            data = _call(token, "getChat", chat_id=r["id"])
            if data.get("ok"):
                full = data["result"]
                r["title"] = full.get("title") or r["title"]
                r["type"] = full.get("type") or r["type"]
    return rows, notes


def main():
    token = (os.environ.get("TG_BOT_TOKEN") or "").strip()
    if not token:
        print("TG_DISCOVER: TG_BOT_TOKEN missing - nothing to do")
        return
    extra = [u for u in (os.environ.get("TG_TRY_USERNAMES") or "").split(",") if u.strip()]
    rows, notes = discover(token, extra)
    print("TG_DISCOVER_BEGIN")
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    for n in notes:
        print("NOTE:", n)
    print("TG_DISCOVER_END")
    chans = [r for r in rows if r["type"] in ("channel", "supergroup")]
    print(f"TG_DISCOVER_SUMMARY: total_chats={len(rows)} channels_or_groups={len(chans)}")


if __name__ == "__main__":
    sys.exit(main())
