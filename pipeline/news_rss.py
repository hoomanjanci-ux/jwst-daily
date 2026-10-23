"""
news_rss.py - FREE official news feeds for the two news channels
(نبض کیهان / COSMIC NEWS), owner-ordered 2026-10-23.

Owner directives implemented here:
  * the news channels pull fresh (and archive-worthy) items from OFFICIAL
    websites: NASA news releases, NASA Webb blog, ESA/Webb news - all FREE RSS;
  * X/Twitter official API is PAID -> rejected (owner red line: zero cost);
  * EVERY news post carries its source link + source name + date (owner rule:
    «هر پستی توی نبض کیهان باید لینک منبعش باشه»);
  * news posts are explicitly labelled official news - NOT analysis (PROMPT_FA §5);
  * topic filter keeps the channels on space/astronomy/JWST (channel identity);
  * archive items get the mandatory «از آرشیو / From the archive» label with the
    ORIGINAL date (PROMPT_FA §5) and never more than ONE per run;
  * FA version: QAI rewrites title+summary into natural Persian (facts ONLY,
    no additions); fallback = original English title + trimmed summary (honest,
    never a fake translation);
  * dedupe via state["news_seen"] (persisted in state.json by run_daily),
    per-language markers so one language failing never blocks the other;
  * hourly RSS polling = event-driven with <=1h latency (PROMPT_FA §5 allows
    news on release; the hourly cron is the delivery vehicle, not the cause).
"""
from __future__ import annotations

import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

import ai_message
import telegram_publish

UA = {"User-Agent": "jwst-free-pipeline/0.3 (official RSS reader; low-volume)"}

FEEDS = [
    {"url": "https://www.nasa.gov/news-release/feed/",
     "source": "NASA", "source_fa": "ناسا"},
    {"url": "https://esawebb.org/news/feed/",
     "source": "ESA/Webb", "source_fa": "اسا/وب (جیمز وب)"},
    {"url": "https://www.nasa.gov/blogs/feed/",
     "source": "NASA Blogs", "source_fa": "وبلاگ‌های ناسا"},
]
# NOTE (verified 2026-10-23): blogs.nasa.gov/webb/feed and webbtelescope.org/news/rss
# return HTML (no RSS). Webb-dedicated coverage comes from the ESA/Webb feed; NASA
# items are kept on-topic by TOPIC_KEYWORDS. X/Twitter API is paid -> not used.

TOPIC_KEYWORDS = ["jwst", "webb", "james webb", "space", "telescope", "galaxy",
                  "star", "stellar", "asteroid", "comet", "meteor", "planet",
                  "exoplanet", "mars", "moon", "lunar", "solar", "sun ", "jupiter",
                  "saturn", "europa", "titan", "pluto", "cosm", "universe",
                  "astronom", "black hole", "nebula", "supernova", "galactic",
                  "orbit", "rocket", "launch", "artemis", "orion", "iss",
                  "space station", "perseverance", "curiosity", "hubble",
                  "spacex", "aurora", "eclipse", "astrophys", "rover", "probe"]

MAX_AGE_DAYS = 10          # fresh-news window; older unseen items -> archive label
SEEN_CAP = 800             # dedupe memory bound (keep newest 500 when exceeded)


def _strip_html(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def _trim(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


_JUNK_PATTERNS = [  # honest cleaning only - removes site chrome, never edits content
    r"(?is)the post .*? appeared first on .*?$",
    r"(?is)\bread (the )?(full )?(story|more|post)\b.*?$",
]


def _clean_summary(raw: str) -> str:
    s = _strip_html(raw)
    m = re.search(r"Discover the cosmos!", s)
    if m:  # APOD items: drop the site-navigation preamble, keep the real text
        s = s[m.start():]
    for p in _JUNK_PATTERNS:
        s = re.sub(p, "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace("[…]", "…").strip(" …-–")


def fetch_feed(url: str) -> list[dict]:
    """Parse RSS2/Atom item/entry nodes into uniform dicts (never raises to caller)."""
    r = requests.get(url, headers=UA, timeout=45)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for it in root.iter():
        if it.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue

        def _g(tag: str, _it=it) -> str:
            for ch in _it:
                if ch.tag.rsplit("}", 1)[-1] == tag:
                    if tag == "link":
                        return ch.get("href") or (ch.text or "").strip()
                    return (ch.text or "").strip()
            return ""

        title = _strip_html(_g("title"))
        link = _g("link") or _g("guid") or _g("id")
        summary = _trim(_clean_summary(_g("description") or _g("summary")), 800)
        date_raw = _g("pubDate") or _g("date") or _g("published") or _g("updated")
        dt = None
        try:
            dt = parsedate_to_datetime(date_raw)
        except Exception:
            dt = None
        if dt is None and date_raw:
            try:
                dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            except Exception:
                dt = None
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        items.append({"id": link, "title": title, "summary": summary, "link": link,
                      "date": dt.astimezone(timezone.utc).isoformat() if dt else "",
                      "dt": dt})
    return items


def on_topic(item: dict) -> bool:
    blob = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return any(k in blob for k in TOPIC_KEYWORDS)


FA_NEWS_PROMPT = (
    "تو سردبیر کانال خبری فارسی «نبض کیهان» هستی. متن زیر یک خبر رسمی فضایی است. "
    "عنوان و خلاصهٔ آن را به فارسی روان، درست و زیبا بازنویسی کن؛ فقط از واقعیت‌های "
    "متن استفاده کن، هیچ چیز اضافه نکن و اغراق نکن. body حداکثر ۳ جملهٔ کوتاه. "
    'فقط JSON برگردان: {"title":"...","body":"..."}'
)


def _glitched(text: str) -> bool:
    """Guard against AI script glitches (e.g. stray CJK tokens inside Persian text).
    Seen in the wild 2026-10-23: «بازم人間の بازگشت» - the run posted it before this
    guard existed; a one-shot fix edited that post, this check prevents a repeat."""
    if re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]", text):
        return True  # kana / CJK / hangul can never be valid inside FA posts
    return len(re.findall(r"[\u0600-\u06FF]", text)) < 10  # no real Persian letters


def _fa_rewrite(item: dict) -> dict | None:
    slim = {"title": item.get("title"), "summary": item.get("summary"),
            "source": item.get("source"), "date": item.get("date")}
    msgs = [{"role": "user", "content": FA_NEWS_PROMPT + "\n\nNEWS ITEM:\n"
             + json.dumps(slim, ensure_ascii=False)[:1500]}]
    for _ in (1, 2):
        try:
            data = ai_message._lenient_json(ai_message._qai_chat(msgs))
            if data and data.get("title") and data.get("body"):
                title, body = str(data["title"])[:160], str(data["body"])[:600]
                if _glitched(title) or _glitched(body):
                    continue  # garbled AI output -> retry, else honest fallback below
                return {"title": title, "body": body}
        except Exception:  # noqa: BLE001 - AI failure -> deterministic fallback
            continue
    return None


def _href(link: str) -> str:
    return html.escape(link or "", quote=True)


def _post_text(item: dict, lang: str, archive: bool) -> str:
    date = (item.get("date") or "")[:10]
    footer = ai_message.build_footer(lang, "news")
    link = _href(item.get("link") or "")
    if lang == "fa":
        rw = _fa_rewrite(item)
        title = html.escape(rw["title"]) if rw else html.escape(item.get("title") or "")
        body = html.escape(rw["body"]) if rw else html.escape(_trim(item.get("summary"), 420))
        src = item.get("source_fa") or item.get("source") or ""
        arch = f"\n🗄 <i>از آرشیو · تاریخ اصلی انتشار: {date}</i>" if archive else ""
        txt = (f"📰 <b>{title}</b>\n\n{body}\n\n"
               f"📡 منبع: {src} · 📅 {date}\n"
               f"🔗 <a href=\"{link}\">متن کامل خبر</a>{arch}\n\n"
               "🏷 نوع: خبر رسمی — نه تحلیل هوش مصنوعی")
    else:
        title = html.escape(item.get("title") or "")
        body = html.escape(_trim(item.get("summary"), 420))
        src = item.get("source") or ""
        arch = f"\n🗄 <i>From the archive · original date: {date}</i>" if archive else ""
        txt = (f"📰 <b>{title}</b>\n\n{body}\n\n"
               f"📡 Source: {src} · 📅 {date}\n"
               f"🔗 <a href=\"{link}\">Full story</a>{arch}\n\n"
               "🏷 Type: official news — not AI analysis")
    return txt + "\n\n" + footer


def publish(state: dict, token: str, targets: list[tuple[str, str, str]]) -> dict:
    """Fetch feeds, dedupe, build FA/EN posts, deliver to the official news targets.
    Never raises (all failures are recorded); marks seen ONLY after a real send."""
    out = {"feeds_checked": len(FEEDS), "feed_errors": {}, "fa": [], "en": [],
           "mode": None, "errors": {}}
    max_per_run = int(os.environ.get("NEWS_MAX_PER_RUN", "2"))
    official = {k: (c, l) for k, c, l in targets if k.endswith("official")}
    tests = [(c, l) for k, c, l in targets if k.startswith("test")]
    if not token or not (official or tests):
        return {"note": "news skipped (no token / no targets)"}

    pool = []
    for f in FEEDS:
        try:
            for it in fetch_feed(f["url"]):
                it["source"], it["source_fa"] = f["source"], f["source_fa"]
                pool.append(it)
        except Exception as e:  # noqa: BLE001 - one dead feed never blocks the rest
            out["feed_errors"][f["source"]] = f"{type(e).__name__}: {str(e)[:80]}"
    pool = [it for it in pool if it.get("id") and it.get("dt") and it.get("title")]

    seen = state.setdefault("news_seen", {})

    def eligible(it: dict, lang: str) -> bool:
        return not (seen.get(it["id"]) or {}).get(lang)

    candidates = [it for it in pool if on_topic(it)
                  and any(eligible(it, l) for l in ("fa", "en"))]
    candidates.sort(key=lambda x: x["dt"], reverse=True)
    now = datetime.now(timezone.utc)
    fresh = [it for it in candidates
             if it["dt"] >= now - timedelta(days=MAX_AGE_DAYS)]
    if fresh:
        chosen, out["mode"] = fresh[:max_per_run], f"fresh ({len(fresh)} unseen)"
    elif candidates:
        chosen, out["mode"] = candidates[:1], "archive (labeled)"
    else:
        chosen = []

    for it in chosen:
        archive = it not in fresh
        for lang in ("fa", "en"):
            if not eligible(it, lang):
                continue
            try:
                text = _post_text(it, lang, archive=archive)
                if official:
                    key = "fa_official" if lang == "fa" else "en_official"
                    chat, _l = official[key]
                    telegram_publish.send_message(token, chat, text)
                    seen.setdefault(it["id"], {})[lang] = now.isoformat()
                    out[lang].append(it["link"])
                else:  # TEST-ONLY: preview to the test channel, do NOT mark seen
                    for c, _l in tests:
                        telegram_publish.send_message(token, c, text)
                    out[lang].append("preview:" + it["link"])
            except Exception as e:  # noqa: BLE001 - per-item isolation
                out["errors"][f"{it['id'][:60]}:{lang}"] = f"{type(e).__name__}: {str(e)[:100]}"

    if len(seen) > SEEN_CAP:  # bound the dedupe memory
        newest = sorted(seen.items(),
                        key=lambda kv: max((kv[1] or {}).values() or ["0"]),
                        reverse=True)[:500]
        state["news_seen"] = dict(newest)
    return out
