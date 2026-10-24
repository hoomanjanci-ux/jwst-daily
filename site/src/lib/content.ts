import raw from "../../data/content.json";

export type Channel = {
  id: string;
  name: string;
  handle: string;
  lang: "fa" | "en";
  kind: "news" | "analysis";
  desc: string;
};

export type Analysis = {
  slug: string;
  product: string;
  published_utc: string | null;
  target: string | null;
  instrument: string | null;
  detector: string | null;
  filter: string | null;
  obs_date: string | null;
  proposal: string | null;
  score: number | null;
  quality_score: number | null;
  image: string | null;
  text_fa: string | null;
  text_en: string | null;
  is_mock: boolean;
};

export type NewsItem = {
  slug: string;
  title: string; // English title (NASA's own wording)
  title_fa?: string | null; // Persian translation — shown inside the post
  summary: string; // English summary
  summary_fa?: string | null; // Persian summary — shown inside the post
  image?: string | null; // article image (feed or og:image)
  link: string;
  source: string;
  source_fa: string;
  date_utc: string | null;
};

export type ContentData = {
  generated_utc: string;
  site: { url: string; channels: Channel[] };
  analyses: Analysis[];
  news: NewsItem[];
};

const data = raw as ContentData;

/** Public analyses only — mock/placeholder analyses never reach the public site. */
export const analyses: Analysis[] = (data.analyses || []).filter((a) => !a.is_mock);

/** Analyses that carry at least one language of rendered text. */
export const analysesWithText = analyses.filter((a) => a.text_fa || a.text_en);

export const news: NewsItem[] = data.news || [];

export const siteChannels: Channel[] = (data.site?.channels || []).filter((c) => c.lang === "fa");

export const faChannels = siteChannels.filter((c) => c.lang === "fa");

export const SITE_URL = data.site?.url || "https://nabzekeyhan.ir";

export const generatedUtc = data.generated_utc;

const faDateFmt = new Intl.DateTimeFormat("fa-IR", {
  timeZone: "Asia/Tehran",
  year: "numeric",
  month: "long",
  day: "numeric",
});
const faTimeFmt = new Intl.DateTimeFormat("fa-IR", {
  timeZone: "Asia/Tehran",
  hour: "2-digit",
  minute: "2-digit",
});

/** Persian date (Jalali, Tehran timezone) — e.g. ۳ آبان ۱۴۰۵ */
export function faDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return faDateFmt.format(d);
}

/** Persian date + time (Tehran) — e.g. ۳ آبان ۱۴۰۵، ۱۷:۰۷ */
export function faDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return `${faDateFmt.format(d)}، ${faTimeFmt.format(d)}`;
}

/** Relative Persian time — «۳ ساعت پیش» */
export function faAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  const rtf = new Intl.RelativeTimeFormat("fa-IR", { numeric: "auto" });
  if (s < 3600) return rtf.format(-Math.round(s / 60), "minute");
  if (s < 86400) return rtf.format(-Math.round(s / 3600), "hour");
  if (s < 86400 * 30) return rtf.format(-Math.round(s / 86400), "day");
  return faDate(iso);
}

/** Human name for the JWST instrument code. */
export function instrumentFa(inst: string | null | undefined): string {
  const map: Record<string, string> = {
    NIRCAM: "NIRCam (مادون قرمز نزدیک)",
    NIRSPEC: "NIRSpec (طیف‌سنج مادون قرمز)",
    MIRI: "MIRI (مادون قرمز میانی)",
    NIRISS: "NIRISS (تصویربرداری و طیف‌سنجی)",
    FGS: "FGS (حسگر نشانه‌یاب)",
  };
  if (!inst) return "";
  return map[inst.toUpperCase()] || inst;
}

export function proposalUrl(pid: string | null | undefined): string | null {
  if (!pid) return null;
  return `https://archive.stsci.edu/proposal-id/${pid}`;
}
