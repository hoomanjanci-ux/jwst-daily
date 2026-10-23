"""
ai_message.py - beautiful per-channel post builder (owner's style package, 2026-10-23).

Implements the owner's style mandate (PROMPT_FA.md sections 5-8):
  * news channels (نبض کیهان / COSMIC NEWS) NEVER present AI output as official news;
  * AI channels (راز کیهان / COSMIC INSIGHT) always label AI assistance and separate
    fact / interpretation / uncertainty;
  * no clickbait, no false certainty, no AI-slop emoji-flood, no raw JSON dumps;
  * message structure: short title -> one-line hook -> clear body -> "why it matters"
    -> source + date -> content-type tag;
  * same-language companion links come from ONE central config (COMPANION below,
    overridable via env TG_COMPANION_JSON), never scattered hard-codes.

Generation strategy (fail-safe):
  1) AI narrative via the free OpenAI-compatible API (QAI_* envs, same creds the
     quality module uses) - facts ONLY from the stored payload, style per the guide.
  2) Any failure / missing API -> deterministic template fallback (still beautiful,
     never blocks the pipeline, never publishes lies).

All Telegram HTML (<b>, <i>, <blockquote>) is emitted here; every interpolated
data value is html.escape()-d. Caption stays <=1024 chars (Bot API hard limit).
"""
from __future__ import annotations

import html
import json
import os

import requests

# ---------------------------------------------------------------- central config
COMPANION = {  # single source of truth for same-language cross-links (section 8)
    "fa": {"news": "@RazKeyhan", "ai": "@NabzeKeyhan1"},
    "en": {"news": "@CosmicInsightJWST", "ai": "@CosmicNewsJWST"},
}

BRAND = {  # channel display names (section 3 mapping)
    "fa": {"news": "نبض کیهان", "ai": "راز کیهان"},
    "en": {"news": "COSMIC NEWS", "ai": "COSMIC INSIGHT"},
}

SELF_LINK = {  # own-channel signature: beautiful self link under EVERY post (owner 2026-10-23)
    "fa": {"news": ("نبض کیهان", "NabzeKeyhan1", "🛰", "تپش قلب کیهان"),
           "ai": ("راز کیهان", "RazKeyhan", "🔭", "رازهای هستی، یک به یک")},
    "en": {"news": ("COSMIC NEWS", "CosmicNewsJWST", "🛰", "Verified, sourced, awe-inspiring"),
           "ai": ("COSMIC INSIGHT", "CosmicInsightJWST", "🔭", "See deeper, understand more")},
}


def build_footer(lang: str, kind: str) -> str:
    """Signature tail modeled on the owner's reference-channel rhythm (tagline + t.me
    link + emoji) WITHOUT its advertising tone. Sibling username comes from the ONE
    central COMPANION config (section 8) - never hard-coded at call sites.

    Owner order 2026-10-23 (applies to FUTURE posts only - past posts are frozen):
    after the tagline + companion lines, the LAST line must show the channel's own
    t.me address EXPLICITLY as visible text («لینکش کامل مشخص باشه»), not only as
    the clickable tagline."""
    kind = "news" if kind == "news" else "ai"
    name, user, emoji, tagline = SELF_LINK[lang][kind]
    other = "ai" if kind == "news" else "news"
    oname, _ouser, oemoji, _tag = SELF_LINK[lang][other]
    ouser = _companion(lang, kind).lstrip("@")  # sibling of THIS channel (central config)
    label = (("تحلیل هوش مصنوعی" if other == "ai" else "اخبار رسمی") if lang == "fa"
             else ("AI analysis" if other == "ai" else "Official news"))
    return "\n".join([
        "———",
        f"{emoji} <b><a href=\"https://t.me/{user}\">{name}</a></b> | {tagline}",
        f"{oemoji} <a href=\"https://t.me/{ouser}\">{label}: {oname}</a> ✨",
        f"🌐 <a href=\"https://t.me/{user}\">t.me/{user}</a>",
    ])


def _companion(lang: str, kind: str) -> str:
    raw = (os.environ.get("TG_COMPANION_JSON", "") or "").strip()
    if raw:  # owner override (central config via env, still ONE place)
        try:
            return (json.loads(raw).get(lang) or {}).get(kind, "") or COMPANION[lang][kind]
        except Exception:  # noqa: BLE001 - malformed override -> defaults
            pass
    return COMPANION[lang][kind]


def _esc(v) -> str:
    return html.escape(str(v or ""))


# ---------------------------------------------------------------- AI narrative
def _qai_chat(messages, timeout=90, max_tokens=500):
    base = (os.environ.get("QAI_BASE_URL", "") or "").strip()
    key = (os.environ.get("QAI_API_KEY", "") or "").strip()
    model = (os.environ.get("QAI_MODEL", "") or "").strip()
    if not (base and key and model):
        return None
    body = {"model": model, "messages": messages, "temperature": 0.4,
            "max_tokens": max_tokens, "response_format": {"type": "json_object"}}
    r = requests.post(base.rstrip("/") + "/chat/completions", json=body,
                      headers={"Authorization": f"Bearer {key}"}, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _lenient_json(content):
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:  # noqa: BLE001
        s, e = content.find("{"), content.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(content[s:e + 1])
            except Exception:  # noqa: BLE001
                return None
    return None


WRITER_PROMPT_FA = (
    "تو سردبیر کانال تلگرامی «راز کیهان» هستی؛ تحلیل‌های فضایی را برای مخاطب عادی "
    "می‌نویسی. فقط از واقعیت‌های دادهٔ خام زیر استفاده کن؛ هیچ ادعایی از خودت نساز "
    "و اگر چیزی در داده نیست، نگو. سه بخش برگردان: hook (حداکثر ۱۲ کلمه، جذاب ولی "
    "بدون اغراق و بدون کلیک‌بیت)، body (۲-۳ جملهٔ روان فارسی، بدون اصطلاح فنی سنگین؛ "
    "بین داده، تفسیر و عدم‌قطعیت مرز بگذار)، why (یک جمله: چرا این مشاهده مهم است). "
    'فقط JSON برگردان: {"hook":"...","body":"...","why":"..."}'
)

WRITER_PROMPT_EN = (
    "You are the editor of the Telegram channel COSMIC INSIGHT, writing space-analysis "
    "posts for a lay audience. Use ONLY the facts in the raw payload below; invent "
    "nothing; if something is absent from the data, do not claim it. Return three "
    "parts: hook (<=12 words, engaging but never clickbait), body (2-3 natural "
    "English sentences, clearly separating data, interpretation and uncertainty), "
    "why (one sentence: why this observation matters). "
    'Reply ONLY with JSON: {"hook":"...","body":"...","why":"..."}'
)


def _ai_narrative(lang: str, payload: dict) -> dict | None:
    """Ask the free model for the 3-part narrative. None on any failure (fail-safe)."""
    prompt = WRITER_PROMPT_FA if lang == "fa" else WRITER_PROMPT_EN
    slim = {k: payload.get(k) for k in
            ("target", "instrument", "filter", "date_obs", "description",
             "proposal_id", "exptime", "title") if payload.get(k)}
    msgs = [{"role": "user", "content": prompt +
             "\n\nRAW PAYLOAD:\n" + json.dumps(slim, ensure_ascii=False)[:1200]}]
    for attempt in (1, 2):
        try:
            data = _lenient_json(_qai_chat(msgs))
            if data and data.get("hook") and data.get("body"):
                return {"hook": str(data["hook"])[:120],
                        "body": str(data["body"])[:600],
                        "why": str(data.get("why") or "")[:200],
                        "generator": "ai"}
        except Exception:  # noqa: BLE001
            continue
    return None


def _fallback_narrative(lang: str, payload: dict) -> dict:
    if lang == "fa":
        return {"hook": f"نمایش تازه‌ای از {_esc(payload.get('target') or 'عمق فضا')}",
                "body": "دادهٔ علمی این مشاهده توسط پایپ‌لاین ما پردازش و رندر شده است؛ "
                        "نسخهٔ تحلیل هوش مصنوعی به‌زودی روی همین پست تکمیل می‌شود.",
                "why": "هر رندر، پنجره‌ای تازه به داده‌های عمومی جیمز وب است.",
                "generator": "template"}
    return {"hook": f"A fresh view of {_esc(payload.get('target') or 'deep space')}",
            "body": "The scientific data of this observation was processed and rendered "
                    "by our pipeline; the AI-assisted analysis will be added here soon.",
            "why": "Every render is a new window into JWST public data.",
            "generator": "template"}


# ---------------------------------------------------------------- builders
def _facts_block(lang: str, meta: dict, proposal: str) -> str:
    if lang == "fa":
        rows = [f"🎯 هدف: <b>{_esc(meta.get('TARGNAME') or '-')}</b>",
                f"🛰 ابزار: {_esc(meta.get('INSTRUME') or '?')} · فیلتر: {_esc(meta.get('FILTER') or '?')}",
                f"📅 تاریخ مشاهده: {_esc(str(meta.get('DATE-OBS') or '')[:10])}"
                + (f" · پروپوزال: {_esc(proposal)}" if proposal else "")]
        return "\n".join(rows)
    rows = [f"🎯 Target: <b>{_esc(meta.get('TARGNAME') or '-')}</b>",
            f"🛰 Instrument: {_esc(meta.get('INSTRUME') or '?')} · filter: {_esc(meta.get('FILTER') or '?')}",
            f"📅 Obs date: {_esc(str(meta.get('DATE-OBS') or '')[:10])}"
            + (f" · proposal: {_esc(proposal)}" if proposal else "")]
    return "\n".join(rows)


def build_post(meta: dict, proposal: str, payload: dict, kind: str, lang: str):
    """Return (caption_html, message_html, gen_note) for one channel kind/lang.
    kind: 'news' | 'ai' | 'test'  (test channel gets the full preview)."""
    target = _esc(meta.get("TARGNAME") or "-")
    dateobs = _esc(str(meta.get("DATE-OBS") or "")[:10])
    brand = BRAND.get(lang, BRAND["en"])

    narr = _ai_narrative(lang, payload) or _fallback_narrative(lang, payload)
    hook, body, why = narr["hook"], narr["body"], narr.get("why", "")
    gen = narr.get("generator", "template")

    if lang == "fa":
        tag_news = "🏷 نوع: دادهٔ رسمی عمومی (MAST/STScI) — نه نتیجهٔ تحلیل"
        tag_ai = "🏷 نوع: تحلیل هوش مصنوعی (AI-assisted)"
        roi_note = "🔲 کادر قرمز: ناحیهٔ منتخب پایپ‌لاین (تشخیص قطعی)"
        news_note = ("🔬 این پست فقط دادهٔ رسمی و پیش‌نمایش است؛ تحلیل هوش مصنوعی "
                     "در کانال همراه ما منتشر می‌شود.")
        ai_label = ("⚠️ <i>این تحلیل با هوش مصنوعی تولید شده است — تفسیر داده است، "
                    "نه گفتهٔ منبع رسمی؛ عدم‌قطعیت‌ها را جدی بگیرید.</i>")
        src = f"📡 <b>منبع:</b> MAST/STScI (دادهٔ عمومی) · 📅 {dateobs}"
        cap_brand = brand["ai"] if kind in ("ai", "test") else brand["news"]
        cap_title = f"🔭 <b>{cap_brand} | {target}</b>"
    else:
        tag_news = "🏷 Type: official public data (MAST/STScI) — not analysis"
        tag_ai = "🏷 Type: AI-assisted analysis"
        roi_note = "🔲 Red box: pipeline-selected ROI (deterministic)"
        news_note = ("🔬 Official data & preview only; AI-assisted analysis lives in "
                     "our companion channel.")
        ai_label = ("⚠️ <i>AI-generated analysis — interpretation of the data, not an "
                    "official statement; uncertainties matter.</i>")
        src = f"📡 <b>Source:</b> MAST/STScI public data · 📅 {dateobs}"
        cap_brand = brand["ai"] if kind in ("ai", "test") else brand["news"]
        cap_title = f"🔭 <b>{cap_brand} | {target}</b>"

    # ---- album caption (shared skeleton, kind-specific tag) ----
    cap_lines = [cap_title, f"<i>{hook}</i>", "", body]
    if why:
        cap_lines += [("", "❓ <b>چرا مهم است؟</b> " + why if lang == "fa"
                      else "❓ <b>Why it matters:</b> " + why)[1]]
    cap_lines += ["", src, tag_ai if kind in ("ai", "test") else tag_news, roi_note]
    footer = build_footer(lang, kind)  # signature tail: own + companion link
    caption = "\n".join(cap_lines)
    budget = 1020 - len(footer) - 1  # Bot API hard limit 1024; footer is never cut
    if len(caption) > budget:
        cut = caption.rfind(">", 0, budget - 1)
        if cut > 0 and "<" in caption[cut:budget]:
            caption = caption[:cut + 1] + "…"   # never tear an HTML tag
        else:
            caption = caption[:budget - 1] + "…"
    caption = caption + "\n" + footer

    # ---- follow-up message ----
    if kind == "news":
        msg = f"🛰 <b>{_esc(brand['news'])}</b>\n{news_note}"
    else:
        facts = _facts_block(lang, meta, proposal)
        ai_head = (f"🤖 <b>تحلیل هوش مصنوعی — {_esc(brand['ai'])}</b>" if lang == "fa"
                   else f"🤖 <b>AI analysis — {_esc(brand['ai'])}</b>")
        msg = (f"{ai_head}\n<blockquote>{body}</blockquote>\n\n"
               f"🔎 <b>{'واقعیت‌ها از متادیتا:' if lang == 'fa' else 'Facts from metadata:'}</b>\n"
               f"{facts}\n\n{ai_label}")
    return caption, msg + "\n\n" + footer, gen
