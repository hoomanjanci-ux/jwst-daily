#!/usr/bin/env python3
"""
site_news_fa.py — Persian translations of the website news feed.

Owner directive (2026-10-24): the website keeps NASA's English headline, but
EVERY news post page must carry the full Persian translation below the English
description. This module:
  * fetches the same 3 official feeds as site/scripts/build-data.mjs,
  * asks QAI (free OpenAI-compatible API) for a natural Persian title+summary,
  * stores them in pipeline/news_site_fa.json keyed by the article link,
  * build-data.mjs merges that file into data/content.json (title_fa/summary_fa).

Design rules:
  * Additive + bounded: at most --cap new translations per run (default 6) so an
    Actions run never burns quota; older items stay until later runs fill them.
  * Never raises: any AI failure just skips that item (retry next run).
  * The JSON cache is committed by the hourly state commit -> Vercel builds
    never call the AI at all.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "pipeline" / "news_site_fa.json"
STATE_PATH = REPO / "pipeline" / "state.json"

FEEDS = [
    "https://www.nasa.gov/news-release/feed/",
    "https://esawebb.org/news/feed/",
    "https://www.nasa.gov/blogs/feed/",
]

TOPIC_KEYWORDS = ["jwst", "webb", "james webb", "space", "telescope", "galaxy",
    "star", "stellar", "asteroid", "comet", "meteor", "planet",
    "exoplanet", "mars", "moon", "lunar", "solar", "sun ", "jupiter",
    "saturn", "europa", "titan", "pluto", "cosm", "universe",
    "astronom", "black hole", "nebula", "supernova", "galactic",
    "orbit", "rocket", "launch", "artemis", "orion", "iss",
    "space station", "perseverance", "curiosity", "hubble",
    "spacex", "aurora", "eclipse", "astrophys", "rover", "probe"]

PROMPT = (
    "تو مترجم حرفه‌ای بخش فضایی یک سایت فارسی هستی. خبر رسمی فضایی زیر را به فارسی "
    "روان و طبیعی برگردان. عنوان را کوتاه و رسا نگه دار (حداکثر ۱۲ کلمه). خلاصه را "
    "۲ تا ۴ جملهٔ روان بنویس؛ فقط واقعیت‌های متن را بیاور، هیچ چیز اضافه نکن و "
    "کلیدواژه‌های فنی (نام تلسکوپ، مأموریت، نهاد) را همان‌طور استاندارد فارسی‌سازی کن "
    "(مثلاً «تلسکوپ فضایی جیمز وب»). اگر متن ورودی به‌هم‌ریخته یا منوهای سایت بود، "
    "فقط از بخش خبری واقعی آن خلاصهٔ درست بساز. "
    'فقط JSON برگردان: {"title_fa":"...","summary_fa":"..."}'
)

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean(raw: str, limit: int = 900) -> str:
    txt = html.unescape(raw or "")
    txt = TAG_RE.sub(" ", txt)
    txt = SPACE_RE.sub(" ", txt).strip()
    return txt[:limit]


def on_topic(title: str, summary: str) -> bool:
    blob = (title + " " + summary).lower()
    return any(k in blob for k in TOPIC_KEYWORDS)


def fetch_items() -> list[dict]:
    items: dict[str, dict] = {}
    ua = {"User-Agent": "jwst-free-pipeline/0.4 (site fa builder; low-volume)"}
    for url in FEEDS:
        try:
            r = requests.get(url, headers=ua, timeout=25)
            if not r.ok:
                continue
            root = ET.fromstring(r.content)
            for el in root.iter():
                tag_end = el.tag.rsplit("}", 1)[-1]
                if tag_end not in ("item", "entry"):
                    continue
                title = link = summary = date = ""
                for ch in el:
                    t = ch.tag.rsplit("}", 1)[-1]
                    if t == "title" and not title:
                        title = clean(ch.text or "", 300)
                    elif t == "link":
                        href = ch.attrib.get("href") or (ch.text or "").strip()
                        if href and not link:
                            link = href
                    elif t in ("description", "summary", "encoded") and not summary:
                        summary = clean(ch.text or "")
                    elif t in ("pubDate", "published", "updated", "date") and not date:
                        date = (ch.text or "").strip()
                if not title or not link or link in items:
                    continue
                if not on_topic(title, summary):
                    continue
                items[link] = {"title": title, "summary": summary[:600],
                               "link": link, "date": date}
        except Exception as e:  # noqa: BLE001 - feed down -> skip
            print(f"[site-fa] feed failed: {url}: {type(e).__name__}", flush=True)
    return sorted(items.values(), key=lambda x: x.get("date") or "", reverse=True)


def qai_translate(title: str, summary: str, key_env: dict | None = None) -> dict | None:
    env = key_env if key_env is not None else os.environ
    base = (env.get("QAI_BASE_URL", "") or "").strip().rstrip("/")
    key = (env.get("QAI_API_KEY", "") or "").strip()
    model = (env.get("QAI_MODEL", "") or "").strip() or "agnes-2.5-flash"
    if not (base and key):
        return None
    slim = json.dumps({"title": title, "summary": summary[:600]}, ensure_ascii=False)
    try:
        r = requests.post(base + "/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "temperature": 0.3, "max_tokens": 450,
                                "response_format": {"type": "json_object"},
                                "messages": [{"role": "user",
                                              "content": PROMPT + "\n\nNEWS ITEM:\n" + slim}]},
                          timeout=95)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        s, e = content.find("{"), content.rfind("}")
        data = json.loads(content[s:e + 1])
        t_fa, s_fa = str(data.get("title_fa") or "").strip()[:160], str(data.get("summary_fa") or "").strip()[:700]
        if not t_fa or not s_fa:
            return None
        if not re.search(r"[\u0600-\u06FF]", t_fa):
            return None  # model answered in English -> skip, retry next run
        return {"title_fa": t_fa, "summary_fa": s_fa}
    except Exception as e:  # noqa: BLE001 - AI failure -> skip quietly
        print(f"[site-fa] translate failed: {type(e).__name__}: {str(e)[:90]}", flush=True)
        return None


def save(store: dict) -> None:
    """Write incrementally — a killed/timeout run must never lose finished work."""
    doc = store.get("_doc", "website Persian translations, keyed by article link (owner 2026-10-24)")
    items = {k: v for k, v in store.items() if not k.startswith("_")}
    out = {"_doc": doc, "items": items}
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT_PATH)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=6, help="max new translations this run")
    ap.add_argument("--min-summary", type=int, default=60,
                    help="skip items whose English summary is shorter than this")
    args = ap.parse_args()

    store: dict = {"_doc": "website Persian translations, keyed by article link (owner 2026-10-24)"}
    if OUT_PATH.exists():
        try:
            old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            items_old = (old.get("items") if isinstance(old, dict) else None) or {}
            store.update(items_old)
        except Exception:  # noqa: BLE001
            pass

    items = fetch_items()
    todo = [it for it in items if it["link"] not in store][: args.cap]
    print(f"[site-fa] feed items: {len(items)} | cached fa: {len(store) - 1} | to do: {len(todo)}", flush=True)

    if not todo:
        print("[site-fa] nothing to translate", flush=True)
        return 0

    # bounded parallelism (owner infra: free API, be gentle) — 3 workers
    from concurrent.futures import ThreadPoolExecutor

    done = 0
    lock_lock = __import__("threading").Lock()

    def work(it: dict) -> None:
        nonlocal done
        fa = qai_translate(it["title"], it["summary"] or it["title"])
        if fa:
            with lock_lock:
                store[it["link"]] = {
                    "title_fa": fa["title_fa"],
                    "summary_fa": fa["summary_fa"],
                    "title_en": it["title"],
                    "date": it["date"],
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                }
                done += 1
                save(store)  # incremental: survive timeout / SIGTERM / crash
            print(f"[site-fa] ok {it['title'][:56]}", flush=True)

    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(work, todo))

    # bound memory: keep newest 220
    core = {k: v for k, v in store.items() if not k.startswith("_")}
    if len(core) > 220:
        keep = sorted(core.items(), key=lambda kv: (kv[1] or {}).get("ts", ""), reverse=True)[:220]
        store = {"_doc": store.get("_doc", "website Persian translations"), **dict(keep)}

    save(store)
    print(f"[site-fa] translated now: {done} | total fa: {len(core)} -> {OUT_PATH.name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
