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
  const desc = (n.summary || n.title).slice(0, 155);
  return {
    title: n.title,
    description: desc,
    alternates: { canonical: `/news/${n.slug}` },
    openGraph: {
      type: "article",
      title: `${n.title} | نبض کیهان`,
      description: desc,
      url: `${SITE_URL}/news/${n.slug}`,
      images: [{ url: "/og-default.jpg" }],
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
    description: n.summary || undefined,
    inLanguage: "fa-IR",
    datePublished: n.date_utc || undefined,
    image: SITE_URL + "/og-default.jpg",
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
          <Link href="/#tazeha" className="hover:text-star">اخبار</Link>
        </nav>

        <h1 className="mb-4 text-2xl font-black leading-relaxed sm:text-3xl sm:leading-relaxed">{n.title}</h1>
        <div className="mb-8 flex flex-wrap items-center gap-3 text-xs text-muted">
          <span className="rounded-full bg-star/15 px-3 py-1 text-star">نبض کیهان · خبر</span>
          <span>منبع: {n.source_fa}</span>
          {n.date_utc && <span className="num-fa">{faDateTime(n.date_utc)}</span>}
        </div>

        {n.summary && (
          <article className="article-body mb-10">
            <p>{n.summary}</p>
          </article>
        )}

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
