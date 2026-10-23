import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import TelegramFab from "@/components/TelegramFab";
import { news, faDateTime, SITE_URL, siteChannels, type NewsItem } from "@/lib/content";

export const dynamicParams = false;

// output:export forbids an empty params array — offline builds (RSS down) get a placeholder.
export const generateStaticParams = () =>
  news.length > 0 ? news.map((n) => ({ slug: n.slug })) : [{ slug: "pending" }];

function getBySlug(slug: string): NewsItem | undefined {
  return news.find((n) => n.slug === slug);
}

function EmptyNews() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto grid min-h-[70vh] max-w-3xl place-items-center px-4 pt-24">
        <div className="card-cosmic p-10 text-center">
          <p className="mb-3 text-5xl">📡</p>
          <h1 className="mb-3 text-2xl font-black">اخبار در حال به‌روزرسانی است</h1>
          <p className="mb-8 text-sm leading-8 text-muted">
            فید خبری رسمی ناسا و اسا در ساعات آینده دوباره این صفحه را پر می‌کند؛
            نسخهٔ لحظه‌ای اخبار در کانال تلگرام نبض کیهان منتشر می‌شود.
          </p>
          <a
            href="https://t.me/NabzeKeyhan1"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-cosmic btn-primary"
          >
            عضویت در نبض کیهان
          </a>
        </div>
      </main>
      <SiteFooter />
      <TelegramFab />
    </>
  );
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const n = getBySlug(slug);
  if (!n) {
    if (news.length === 0) return { title: "اخبار — به‌زودی", robots: { index: false, follow: true } };
    return {};
  }
  const desc = (n.summary_fa || n.summary || n.title).slice(0, 155);
  return {
    title: n.title_fa || n.title,
    description: desc,
    alternates: { canonical: `/news/${n.slug}` },
    openGraph: {
      type: "article",
      title: `${n.title} | نبض کیهان`,
      description: desc,
      url: `${SITE_URL}/news/${n.slug}`,
      images: [{ url: n.image || "/og-default.jpg" }],
    },
  };
}

export default async function NewsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const n = getBySlug(slug);
  if (!n) {
    if (news.length === 0) return <EmptyNews />;
    notFound();
  }

  const nabzChan = siteChannels.find((c) => c.id === "fa_news");
  const ld = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: n.title,
    alternativeHeadline: n.title_fa || undefined,
    description: n.summary_fa || n.summary || undefined,
    inLanguage: "fa-IR",
    datePublished: n.date_utc || undefined,
    image: (n.image || SITE_URL + "/og-default.jpg") as string,
    author: { "@type": "Organization", name: n.source_fa, url: n.link },
    publisher: { "@type": "Organization", name: "نبض کیهان", url: SITE_URL },
    isBasedOn: n.link,
  };

  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-4xl px-4 pb-24 pt-28">
        <nav className="mb-6 text-xs text-muted" aria-label="مسیر">
          <Link href="/" className="hover:text-star">خانه</Link>
          <span className="mx-2">/</span>
          <Link href="/?tab=news#tazeha" className="hover:text-star">اخبار</Link>
        </nav>

        {/* English headline (owner: NASA's own wording) */}
        <h1 className="mb-3 text-2xl font-black leading-relaxed sm:text-3xl sm:leading-relaxed" dir="ltr" style={{ textAlign: "start" }}>
          {n.title}
        </h1>
        {n.title_fa && (
          <p className="mb-4 text-lg font-bold leading-8 text-ink/90 sm:text-xl">{n.title_fa}</p>
        )}
        <div className="mb-8 flex flex-wrap items-center gap-3 text-xs text-muted">
          <span className="rounded-full bg-star/15 px-3 py-1 text-star">نبض کیهان · خبر</span>
          <span>منبع: {n.source_fa}</span>
          {n.date_utc && <span className="num-fa">{faDateTime(n.date_utc)}</span>}
          {/* owner 2026-10-24: the promise in parentheses */}
          <span className="rounded-full bg-gold/10 px-3 py-1 text-gold/90">
            (توضیحات فارسی کامل داخل همین پست)
          </span>
        </div>

        {n.image && (
          <figure className="mb-8 overflow-hidden rounded-2xl border border-line">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={n.image} alt={n.title_fa || n.title} className="news-hero-img" loading="eager" />
            <figcaption className="bg-panel/60 px-4 py-2 text-center text-[11px] text-muted">
              تصویر: {n.source} (اعتبار: NASA)
            </figcaption>
          </figure>
        )}

        {/* English original (owner: English first, we keep it as the source) */}
        {n.summary && (
          <section className="mb-8" aria-label="متن اصلی خبر">
            <h2 className="mb-3 text-xs font-bold tracking-wider text-muted" dir="ltr">— ORIGINAL (ENGLISH) —</h2>
            <article className="article-body" dir="ltr">
              <p style={{ textAlign: "start" }}>{n.summary}</p>
            </article>
          </section>
        )}

        {/* Persian translation — below the English (owner directive) */}
        <section className="mb-10" aria-label="ترجمهٔ فارسی">
          <h2 className="sec-title mb-4 text-xl">
            ترجمهٔ فارسی<span className="bar" />
          </h2>
          {n.summary_fa ? (
            <article className="article-body card-cosmic p-5 sm:p-7">
              {n.title_fa && <p className="mb-3 text-base font-black text-ink">{n.title_fa}</p>}
              <p>{n.summary_fa}</p>
            </article>
          ) : (
            <p className="card-cosmic p-5 text-sm leading-8 text-muted">
              ترجمهٔ فارسی این خبر به‌زودی به همین صفحه اضافه می‌شود؛ نسخهٔ فارسی آن هم‌اکنون در
              کانال تلگرام «نبض کیهان» منتشر شده است.
            </p>
          )}
        </section>

        <div className="card-cosmic mb-10 flex flex-col items-start gap-4 p-6">
          <p className="text-sm leading-7 text-muted">
            ادامهٔ این خبر در منبع رسمی منتشر شده است. برای پوشش فارسی اخبار فضا، همراه نبض کیهان باشید.
          </p>
          <div className="flex flex-wrap gap-3">
            <a href={n.link} target="_blank" rel="noopener noreferrer" className="btn-cosmic btn-ghost text-sm">
              منبع رسمی ↗
            </a>
            <a
              href={`https://t.me/${nabzChan?.handle || "NabzeKeyhan1"}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-cosmic btn-primary text-sm"
            >
              عضویت در نبض کیهان
            </a>
          </div>
        </div>
      </main>
      <SiteFooter />
      <TelegramFab />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld) }} />
    </>
  );
}
