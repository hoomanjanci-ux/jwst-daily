"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { analyses, news, faAgo, instrumentFa, type Analysis, type NewsItem } from "@/lib/content";

type Tab = "all" | "analysis" | "news";

function Thumb({ image, alt, code }: { image: string | null; alt: string; code: string }) {
  if (image) {
    return (
      <div className="tile-thumb">
        <img src={image} alt={alt} loading="lazy" />
      </div>
    );
  }
  const hue = [...code].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
  return (
    <div className="tile-thumb grid place-items-center">
      <div
        className="absolute inset-0 opacity-70"
        style={{
          background:
            `radial-gradient(90% 90% at ${25 + (hue % 40)}% 20%, hsla(${hue},70%,60%,0.35), transparent 60%),` +
            `radial-gradient(100% 100% at 80% 85%, hsla(${(hue + 60) % 360},80%,55%,0.3), transparent 55%),` +
            `linear-gradient(160deg,#0b1230,#050814)`,
        }}
      />
      <span className="relative z-10 px-3 text-center font-mono text-[11px] tracking-wider text-ink/70" dir="ltr">
        {code.slice(0, 22)}
      </span>
      <span className="absolute bottom-2 left-2 z-10 rounded-full bg-void/60 px-2 py-0.5 text-[10px] text-star">
        JWST
      </span>
    </div>
  );
}

function AnalysisCard({ a }: { a: Analysis }) {
  const title =
    a.text_fa?.split("\n").find((l) => l.trim() && !l.trim().startsWith("🌐") && !l.trim().startsWith("—"))?.trim().slice(0, 80) ||
    (a.target ? `تحلیل دادهٔ ${a.target}` : `تحلیل دادهٔ جیمز وب — ${a.product.slice(0, 18)}`);
  return (
    <Link
      href={`/post/${a.slug}`}
      className="group card-cosmic flex flex-col overflow-hidden"
      aria-label={title}
    >
      <Thumb image={a.image} alt={title} code={a.product} />
      <div className="flex flex-1 flex-col p-4">
        <h3 className="mb-2 line-clamp-2 font-bold leading-7 transition-colors group-hover:text-star">{title}</h3>
        <div className="mt-auto flex flex-wrap items-center gap-2 text-[11px] text-muted">
          <span className="rounded-full bg-nebula/15 px-2 py-0.5 text-nebula">راز کیهان · تحلیل</span>
          {a.instrument && <span className="rounded-full bg-line/50 px-2 py-0.5">{instrumentFa(a.instrument).split(" (")[0]}</span>}
          {a.obs_date && <span>رصد: {a.obs_date}</span>}
          {a.published_utc && <span className="num-fa">{faAgo(a.published_utc)}</span>}
        </div>
      </div>
    </Link>
  );
}

function NewsCard({ n }: { n: NewsItem }) {
  return (
    <Link
      href={`/news/${n.slug}`}
      className="group card-cosmic flex flex-col overflow-hidden"
      aria-label={n.title}
    >
      <Thumb image={null} alt={n.title} code={n.source} />
      <div className="flex flex-1 flex-col p-4">
        <h3 className="mb-2 line-clamp-2 font-bold leading-7 transition-colors group-hover:text-star">{n.title}</h3>
        {n.summary && <p className="mb-3 line-clamp-2 text-xs leading-6 text-muted">{n.summary}</p>}
        <div className="mt-auto flex flex-wrap items-center gap-2 text-[11px] text-muted">
          <span className="rounded-full bg-star/15 px-2 py-0.5 text-star">نبض کیهان · خبر</span>
          <span>{n.source_fa}</span>
          {n.date_utc && <span className="num-fa">{faAgo(n.date_utc)}</span>}
        </div>
      </div>
    </Link>
  );
}

export default function Feed() {
  const [tab, setTab] = useState<Tab>("all");

  const { aList, nList } = useMemo(() => ({ aList: analyses, nList: news }), []);

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: "all", label: "همه", count: aList.length + nList.length },
    { id: "analysis", label: "تحلیل‌ها — راز کیهان", count: aList.length },
    { id: "news", label: "اخبار — نبض کیهان", count: nList.length },
  ];

  const shown = useMemo(() => {
    const items: { key: string; el: React.ReactNode; t: number }[] = [];
    if (tab !== "news")
      aList.forEach((a) =>
        items.push({
          key: "a-" + a.slug,
          t: new Date(a.published_utc || 0).getTime() || 0,
          el: <AnalysisCard a={a} />,
        })
      );
    if (tab !== "analysis")
      nList.forEach((n) =>
        items.push({ key: "n-" + n.slug, t: new Date(n.date_utc || 0).getTime() || 0, el: <NewsCard n={n} /> })
      );
    items.sort((x, y) => y.t - x.t);
    return items;
  }, [tab, aList, nList]);

  return (
    <div>
      {/* tabs */}
      <div className="mb-8 flex flex-wrap items-center gap-2" role="tablist" aria-label="فیلتر محتوا">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition-all duration-200 ${
              tab === t.id
                ? "bg-gradient-to-l from-star to-nebula text-void shadow-[0_6px_24px_rgba(111,183,255,0.35)]"
                : "border border-line bg-panel/60 text-muted hover:border-star/50 hover:text-ink"
            }`}
          >
            {t.label}
            <span className="num-fa mr-1.5 opacity-70">({t.count.toLocaleString("fa-IR")})</span>
          </button>
        ))}
      </div>

      {/* grid */}
      {shown.length === 0 ? (
        <div className="card-cosmic grid place-items-center px-6 py-16 text-center">
          <p className="mb-2 text-4xl">🔭</p>
          <p className="mb-1 font-bold">به‌زودی</p>
          <p className="mb-6 text-sm leading-7 text-muted">
            اولین تحلیل‌ها و اخبار در همین بخش ظاهر می‌شوند. تا آن زمان، در تلگرام همراه ما باشید.
          </p>
          <a
            href="https://t.me/RazKeyhan"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-cosmic btn-primary text-sm"
          >
            دنبال کردن راز کیهان در تلگرام
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((it) => (
            <div key={it.key}>{it.el}</div>
          ))}
        </div>
      )}
    </div>
  );
}
