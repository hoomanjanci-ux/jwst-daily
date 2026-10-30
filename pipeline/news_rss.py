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
    no additions); fallback = validated Persian translation through a free public
    translation endpoint. If neither succeeds, hold FA for retry; NEVER post English;
  * dedupe via state["news_seen"] (persisted in state.json by run_daily),
    per-language markers so one language failing never blocks the other;
  * hourly RSS polling = event-driven with <=1h latency (PROMPT_FA §5 allows
    news on release; the hourly cron is the delivery vehicle, not the cause).
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
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

# ---- L5 anti-duplicate (owner directive 2026-10-24, TOP priority) -------------
# The same story reaches us through DIFFERENT official feeds with different URLs
# (e.g. one release on nasa.gov/news-release AND on the blogs feed), and SEEN_CAP
# eviction could theoretically re-surface a years-old URL. Two extra permanent
# layers close both holes:
#   news_title_fp      exact title fingerprint, kept ~2+ years (cap 6000 entries,
#                      ~60 B each -> a few hundred KB in state.json - bounded)
#   news_title_recent  recent normalized titles for FUZZY matching (cap 300):
#                      near-identical title from another feed = same story -> skipped
TITLE_FP_CAP = 6000
RECENT_TITLES_CAP = 300
FUZZY_TITLE_RATIO = 0.80


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", (t or "").lower()).strip()


def _title_fp(t: str) -> str:
    return hashlib.sha1(_norm_title(t).encode("utf-8")).hexdigest()[:16]


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


def _log(msg):
    """Live progress line for the news phase (2026-10-23: 40 silent minutes were
    undiagnosable because this module never printed anything)."""
    print(f"[jwst-news {time.strftime('%H:%M:%S', time.gmtime())} UTC] {msg}", flush=True)


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


def _glitched(text: str, minimum: int = 2) -> bool:
    """Require predominantly Persian prose, not merely a few Persian characters.
    Keep Latin mission names/acronyms possible; reject unrelated scripts.
    """
    if not isinstance(text, str) or not text.strip():
        return True
    if re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]", text):
        return True
    letters = [c for c in text if c.isalpha()]
    persian = [c for c in letters if '\u0600' <= c <= '\u06ff']
    return len(persian) < minimum or len(persian) / max(1, len(letters)) < 0.60


def _valid_fa_rewrite(data: dict | None) -> bool:
    return (isinstance(data, dict)
            and isinstance(data.get('title'), str) and isinstance(data.get('body'), str)
            and not _glitched(data['title'], 2) and not _glitched(data['body'], 12))


def _translate_fa(text: str) -> str:
    # Public news text only; no credentials/private data. Unofficial free endpoint:
    # availability is not assumed, and failure never permits English publication.
    if not text:
        return ''
    for host in ('translate.googleapis.com', 'translate.google.com'):
        try:
            r = requests.get('https://' + host + '/translate_a/single',
                             params={'client': 'gtx', 'sl': 'en', 'tl': 'fa', 'dt': 't', 'q': text},
                             headers={'User-Agent': 'Mozilla/5.0'}, timeout=(5, 15))
            r.raise_for_status()
            result = ''.join(part[0] for part in r.json()[0]
                             if part and isinstance(part[0], str)).strip()
            if not _glitched(result):
                return result
        except Exception as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            _log(f"FA backup {host}: {type(e).__name__}, HTTP {status}")
    # Second independent, keyless service; public source text only. Honor its
    # per-request limit. Quota/failure is rejected rather than posted as news.
    chunks=[];remaining=text
    while remaining:
        chunk=remaining[:400]
        if len(remaining)>400 and ' ' in chunk:
            chunk=chunk.rsplit(' ',1)[0]
        chunks.append(chunk);remaining=remaining[len(chunk):].lstrip()
    translated=[]
    for chunk in chunks:
        r=requests.get('https://api.mymemory.translated.net/get',
                       params={'q':chunk,'langpair':'en|fa'},headers=UA,timeout=(5,15))
        r.raise_for_status();data=r.json()
        if data.get('responseStatus')!=200:
            raise ValueError('FA backup unavailable or quota exceeded')
        value=(data.get('responseData') or {}).get('translatedText') or ''
        if _glitched(value):raise ValueError('FA backup returned non-Persian content')
        translated.append(html.unescape(value))
    return ' '.join(translated)


def _fa_rewrite(item: dict) -> dict | None:
    slim = {"title": item.get("title"), "summary": item.get("summary"),
            "source": item.get("source"), "date": item.get("date")}
    msgs = [{"role": "user", "content": FA_NEWS_PROMPT + "\n\nNEWS ITEM:\n"
             + json.dumps(slim, ensure_ascii=False)[:1500]}]
    for _ in (1, 2):
        try:
            data = ai_message._lenient_json(ai_message._qai_chat(
                msgs, timeout=(5, 20), max_tokens=650))
            if _valid_fa_rewrite(data):
                result = {'title': _trim(data['title'], 160), 'body': _trim(data['body'], 600)}
                if _valid_fa_rewrite(result):
                    return result
        except Exception as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            _log(f"FA writer unavailable: {type(e).__name__}, HTTP {status}")
            continue
    try:
        result = {'title': _trim(_translate_fa(item.get('title') or ''), 160),
                  'body': _trim(_translate_fa(_trim(item.get('summary') or '', 800)), 600)}
        if _valid_fa_rewrite(result):
            return result
    except Exception as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        _log(f"FA translation held: {type(e).__name__}, HTTP {status}")
    return None  # FA stays unseen/retryable. English delivery is independent.


def _href(link: str) -> str:
    return html.escape(link or "", quote=True)


def _post_text(item: dict, lang: str, archive: bool, fa_rw: dict | None = None) -> str:
    date = (item.get("date") or "")[:10]
    footer = ai_message.build_footer(lang, "news")
    link = _href(item.get("link") or "")
    if lang == "fa":
        rw = fa_rw if fa_rw is not None else _fa_rewrite(item)
        if not _valid_fa_rewrite(rw):
            raise ValueError("Persian news translation unavailable; held for retry, not sent in English")
        title = html.escape(rw["title"])
        body = html.escape(rw["body"])
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
    Official news NEVER goes to the AI-analysis channels (owner rule 2026-10-24).
    Never raises (all failures are recorded); marks seen ONLY after a real send."""
    out = {"feeds_checked": len(FEEDS), "feed_errors": {}, "fa": [], "en": [],
           "mode": None, "errors": {}}
    max_per_run = int(os.environ.get("NEWS_MAX_PER_RUN", "2"))
    official = {k: (c, l) for k, c, l in targets if k.endswith("official")}
    if not token or not official:
        return {"note": "news skipped (no token / no official-news channels configured)"}

    pool = []
    for f in FEEDS:
        try:
            for it in fetch_feed(f["url"]):
                it["source"], it["source_fa"] = f["source"], f["source_fa"]
                pool.append(it)
        except Exception as e:  # noqa: BLE001 - one dead feed never blocks the rest
            out["feed_errors"][f["source"]] = f"{type(e).__name__}: {str(e)[:80]}"
    pool = [it for it in pool if it.get("id") and it.get("dt") and it.get("title")]
    _log(f"feeds done: pool={len(pool)} items, feed_errors={len(out['feed_errors'])}")

    seen = state.setdefault("news_seen", {})
    tfp = state.setdefault("news_title_fp", {})        # L5 exact-title layer
    recent = state.setdefault("news_title_recent", [])  # L5 fuzzy-title layer

    def eligible(it: dict, lang: str) -> bool:
        return not (seen.get(it["id"]) or {}).get(lang)

    def _exact_langs(it: dict) -> set:
        return set((tfp.get(_title_fp(it.get("title") or "")) or {}).keys())

    def _near_dup(it: dict) -> bool:
        fp_self = _title_fp(it.get("title") or "")
        nt = _norm_title(it.get("title") or "")
        if not nt:
            return False
        for f, t80 in recent[-RECENT_TITLES_CAP:]:
            if f == fp_self:
                # own story identity (e.g. fa retry after only en went out) -
                # the same story re-surfacing is handled by the exact layer
                continue
            if t80 and SequenceMatcher(None, nt, t80).ratio() >= FUZZY_TITLE_RATIO:
                return True
        return False

    candidates = []
    for it in pool:
        if not on_topic(it):
            continue
        if not any(eligible(it, l) and l not in _exact_langs(it)
                   for l in ("fa", "en")):
            continue
        if _near_dup(it):  # same story via another official feed/URL
            _log(f"NEAR-DUPLICATE title skipped: {(it.get('title') or '')[:60]}")
            continue
        candidates.append(it)
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
    _log(f"chosen {len(chosen)} items (mode={out['mode']})")

    for it in chosen:
        _log(f"item: {(it.get('title') or '')[:60]}")
        archive = it not in fresh
        fp = _title_fp(it.get("title") or "")  # L5 story identity
        if not any(f == fp for f, _t in recent[-RECENT_TITLES_CAP:]):
            recent.append([fp, _norm_title(it.get("title") or "")[:80]])
        fa_rw: dict | None = None  # computed once, reused by post + site archive
        for lang in ("fa", "en"):
            if not eligible(it, lang) or lang in _exact_langs(it):
                continue
            try:
                if lang == "fa" and fa_rw is None:
                    fa_rw = _fa_rewrite(it)
                    if not _valid_fa_rewrite(fa_rw):
                        raise ValueError("Persian news translation unavailable; held for retry")
                text = _post_text(it, lang, archive=archive, fa_rw=fa_rw)
                key = "fa_official" if lang == "fa" else "en_official"
                if key in official:
                    chat, _l = official[key]
                    telegram_publish.send_message(token, chat, text)
                    _log(f"SENT {lang} -> {key} | {(it.get('title') or '')[:50]}")
                    seen.setdefault(it["id"], {})[lang] = now.isoformat()
                    tfp.setdefault(fp, {})[lang] = now.isoformat()[:10]  # L5 mark
                    out[lang].append(it["link"])
                    # site archive (additive; website feed reads this; posting ignores it)
                    if lang == "fa":
                        try:
                            arch = state.setdefault("news_archive", {})
                            arch[it["id"]] = {
                                "title": (fa_rw or {}).get("title") or it.get("title") or "",
                                "summary": (fa_rw or {}).get("body") or _trim(it.get("summary"), 420),
                                "link": it.get("link") or "",
                                "source": it.get("source") or "",
                                "source_fa": it.get("source_fa") or "",
                                "date": it.get("date") or "",
                                "ts": now.isoformat(),
                            }
                            if len(arch) > 150:  # bound memory: keep newest
                                keep = sorted(arch.items(), key=lambda kv: (kv[1] or {}).get("ts", ""),
                                              reverse=True)[:150]
                                state["news_archive"] = dict(keep)
                        except Exception:  # noqa: BLE001 - archive must never break posting
                            pass
            except Exception as e:  # noqa: BLE001 - per-item isolation
                out["errors"][f"{it['id'][:60]}:{lang}"] = f"{type(e).__name__}: {str(e)[:100]}"

    if len(seen) > SEEN_CAP:  # bound the dedupe memory
        newest = sorted(seen.items(),
                        key=lambda kv: max((kv[1] or {}).values() or ["0"]),
                        reverse=True)[:500]
        state["news_seen"] = dict(newest)
    if len(tfp) > TITLE_FP_CAP:  # L5: ~2+ years of titles; keep the newest
        newest = sorted(tfp.items(),
                        key=lambda kv: max((kv[1] or {}).values() or ["0"]),
                        reverse=True)[:TITLE_FP_CAP - 1000]
        state["news_title_fp"] = dict(newest)
    if len(recent) > RECENT_TITLES_CAP:
        state["news_title_recent"] = recent[-RECENT_TITLES_CAP:]
    return out
