#!/usr/bin/env node
/**
 * build-data.mjs — builds site/data/content.json from the jwst-daily repository.
 *
 * Sources (repo-relative, run from site/):
 *   ../analyses  (recursive) .fits.json  analysis metadata (MAST products)
 *   ../analyses  (recursive) .post.json  rendered Telegram content (fa/en) - future posts
 *   ../analyses  (recursive) .jpg        archived MAST preview images - future posts
 *   3 official RSS feeds: NASA news-release / ESA-Webb / NASA Blogs
 *                         (same topic filter as pipeline/news_rss.py)
 *
 * Output contract for the Next.js app:
 *   data/content.json  { generated_utc, site:{url,channels[]}, analyses[], news[] }
 *   public/img/<slug>.jpg          copied archived images
 *   public/og.jpg                  og:image (latest archived analysis image or none)
 *
 * Design rules:
 *   - Zero npm dependencies (runs identically on Vercel build and locally).
 *   - RSS fetch is NON-FATAL: offline builds fall back to analyses only.
 *   - Never touches pipeline code or state — read-only over ../analyses.
 */
import { readdirSync, statSync, existsSync, readFileSync, writeFileSync, mkdirSync, copyFileSync } from "node:fs";
import { join, relative, dirname, basename } from "node:path";

const SITE_DIR = process.cwd();
const REPO_DIR = join(SITE_DIR, "..");
const ANALYSES_DIR = join(REPO_DIR, "analyses");
const DATA_DIR = join(SITE_DIR, "data");
const IMG_DIR = join(SITE_DIR, "public", "img");

const SITE_URL = "https://nabzekeyhan.ir";
const UA = { headers: { "User-Agent": "jwst-free-pipeline/0.3 (site data builder; low-volume)" } };

// Same topic filter as pipeline/news_rss.py (single source of truth for scope)
const TOPIC_KEYWORDS = ["jwst", "webb", "james webb", "space", "telescope", "galaxy",
  "star", "stellar", "asteroid", "comet", "meteor", "planet",
  "exoplanet", "mars", "moon", "lunar", "solar", "sun ", "jupiter",
  "saturn", "europa", "titan", "pluto", "cosm", "universe",
  "astronom", "black hole", "nebula", "supernova", "galactic",
  "orbit", "rocket", "launch", "artemis", "orion", "iss",
  "space station", "perseverance", "curiosity", "hubble",
  "spacex", "aurora", "eclipse", "astrophys", "rover", "probe"];

const FEEDS = [
  { url: "https://www.nasa.gov/news-release/feed/", source: "NASA", source_fa: "ناسا" },
  { url: "https://esawebb.org/news/feed/", source: "ESA/Webb", source_fa: "اسا/وب (جیمز وب)" },
  { url: "https://www.nasa.gov/blogs/feed/", source: "NASA Blogs", source_fa: "وبلاگ‌های ناسا" },
];

const CHANNELS = [
  { id: "fa_news", name: "نبض کیهان", handle: "NabzeKeyhan1", lang: "fa", kind: "news", desc: "اخبار رسمی فضا از ناسا و اسا — به فارسی" },
  { id: "fa_ai", name: "راز کیهان", handle: "RazKeyhan", lang: "fa", kind: "analysis", desc: "تحلیل هوش مصنوعی از داده‌های خام جیمز وب" },
  { id: "en_news", name: "COSMIC NEWS", handle: "CosmicNewsJWST", lang: "en", kind: "news", desc: "Official space news, in English" },
  { id: "en_ai", name: "COSMIC INSIGHT", handle: "CosmicInsightJWST", lang: "en", kind: "analysis", desc: "AI analysis of raw JWST data, in English" },
];

const slugify = (s) => s.toLowerCase().replace(/\.fits$/i, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const stableHash = (s) => {
  let h = 5381;
  for (const c of s) h = ((h * 33) ^ c.charCodeAt(0)) >>> 0;
  return h.toString(36);
};
const isTopic = (t) => {
  const b = (t || "").toLowerCase();
  return TOPIC_KEYWORDS.some((k) => b.includes(k));
};

// ---------- analyses ----------
function walk(dir, acc = []) {
  if (!existsSync(dir)) return acc;
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, acc);
    else acc.push(p);
  }
  return acc;
}

function buildAnalyses() {
  if (!existsSync(ANALYSES_DIR)) return [];
  const out = [];
  for (const f of walk(ANALYSES_DIR)) {
    if (!f.endsWith(".fits.json")) continue;
    try {
      const j = JSON.parse(readFileSync(f, "utf-8"));
      const stem = basename(f).replace(/\.fits\.json$/i, "");
      const slug = slugify(stem);
      const postPath = join(dirname(f), stem + ".post.json");
      const imgRel = join(dirname(f), stem + ".jpg");
      const imgLocal = join(IMG_DIR, slug + ".jpg");

      let items = null;
      if (existsSync(postPath)) {
        items = (JSON.parse(readFileSync(postPath, "utf-8")).items) || null;
      }
      const pick = (k) => {
        if (!items) return null;
        const a = items[`ai_${k}`] || items[`news_${k}`] || items[`test_${k}`] || null;
        return a ? (a.text || a.caption || null) : null;
      };

      let image = null;
      if (existsSync(imgRel)) {
        mkdirSync(IMG_DIR, { recursive: true });
        copyFileSync(imgRel, imgLocal);
        image = "/img/" + slug + ".jpg";
      }

      out.push({
        slug,
        product: j.product || stem + ".fits",
        published_utc: (items && Object.values(items).length && j.ts) || j.ts || null,
        target: j.meta?.TARGNAME || null,
        instrument: j.meta?.INSTRUME || null,
        detector: j.meta?.DETECTOR || null,
        filter: j.meta?.FILTER || null,
        obs_date: j.meta?.["DATE-OBS"] || null,
        proposal: j.proposal || j.meta?.PROPOSID || null,
        score: typeof j.score === "number" ? j.score : null,
        quality_score: j.quality?.score ?? null,
        image,
        text_fa: pick("fa"),
        text_en: pick("en"),
        is_mock: Boolean(j.mock_analysis?.mock),
      });
    } catch { /* one bad file must not kill the build */ }
  }
  out.sort((a, b) => String(b.published_utc || "").localeCompare(String(a.published_utc || "")));
  return out;
}

// ---------- RSS (tiny parser: RSS2 <item> + Atom <entry>) ----------
const decode = (s) => (s || "")
  .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
  .replace(/&#39;|&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
  .replace(/&amp;/g, "&").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

const tag = (block, names) => {
  for (const n of names) {
    const m = block.match(new RegExp(`<${n}[^>]*>([\\s\\S]*?)</${n}>`, "i"));
    if (m) return decode(m[1]);
  }
  return null;
};

async function buildNews() {
  const seen = new Set();
  const items = [];
  await Promise.all(FEEDS.map(async (f) => {
    try {
      const res = await fetch(f.url, { ...UA, signal: AbortSignal.timeout(20000) });
      if (!res.ok) return;
      const xml = await res.text();
      const blocks = [
        ...xml.matchAll(/<item[\s>][\s\S]*?<\/item>/gi),
        ...xml.matchAll(/<entry[\s>][\s\S]*?<\/entry>/gi),
      ];
      for (const b of blocks) {
        const block = b[0];
        const title = tag(block, ["title"]);
        let link = tag(block, ["link"]);
        if (!link) {
          const m = block.match(/<link[^>]*href="([^"]+)"/i);
          link = m ? m[1] : null;
        }
        const summary = tag(block, ["description", "summary", "content:encoded"]);
        const date = tag(block, ["pubDate", "published", "updated", "dc:date"]);
        if (!title || !link || seen.has(link)) continue;
        if (!isTopic(title + " " + (summary || ""))) continue;
        seen.add(link);
        const host = new URL(link).hostname.replace(/^www\./, "");
        items.push({
          slug: host.split(".")[0] + "-" + stableHash(link),
          title,
          summary: (summary || "").slice(0, 320),
          link,
          source: f.source,
          source_fa: f.source_fa,
          date_utc: date ? new Date(date).toISOString() || null : null,
        });
      }
    } catch { /* feed down / offline -> skip silently */ }
  }));
  items.sort((a, b) => String(b.date_utc || "").localeCompare(String(a.date_utc || "")));
  return items.slice(0, 30);
}

// ---------- main ----------
mkdirSync(DATA_DIR, { recursive: true });
mkdirSync(IMG_DIR, { recursive: true });

const [analyses, news] = [buildAnalyses(), await buildNews()];

// og:image: latest archived analysis image, else keep existing og.jpg
if (analyses[0]?.image && existsSync(join(SITE_DIR, "public", analyses[0].image))) {
  copyFileSync(join(SITE_DIR, "public", analyses[0].image), join(SITE_DIR, "public", "og.jpg"));
}

const doc = {
  generated_utc: new Date().toISOString(),
  site: { url: SITE_URL, channels: CHANNELS },
  analyses,
  news,
};

writeFileSync(join(DATA_DIR, "content.json"), JSON.stringify(doc, null, 1), "utf-8");
console.log(`content.json: ${analyses.length} analyses (${analyses.filter(a => a.image).length} with image, ${analyses.filter(a => a.text_fa || a.text_en).length} with text), ${news.length} news items`);
