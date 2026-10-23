import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import TelegramFab from "@/components/TelegramFab";
import {
  analyses,
  faDateTime,
  instrumentFa,
  proposalUrl,
  SITE_URL,
  siteChannels,
  type Analysis,
} from "@/lib/content";

export const dynamicParams = false;

// output:export forbids an empty params array — when no public analyses exist
// yet, we generate one placeholder page that renders a friendly empty state.
export const generateStaticParams = () =>
  analyses.length > 0 ? analyses.map((a) => ({ slug: a.slug })) : [{ slug: "pending" }];

function getBySlug(slug: string): Analysis | undefined {
  return analyses.find((a) => a.slug === slug);
}

function EmptyAnalyses() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto grid min-h-[70vh] max-w-3xl place-items-center px-4 pt-24">
        <div className="card-cosmic p-10 text-center">
          <p className="mb-3 text-5xl">🔭</p>
          <h1 className="mb-3 text-2xl font-black">اولین تحلیل‌ها در راه است</h1>
          <p className="mb-8 text-sm leading-8 text-muted">
            موتور تحلیل «راز کیهان» در حال آماده‌سازی اولین بسته از داده‌های خام جیمز وب است؛
            همین صفحه به‌محض انتشار، به آرشیو کامل تحلیل‌ها تبدیل می‌شود.
          </p>
          <a
            href="https://t.me/RazKeyhan"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-cosmic btn-primary"
          >
            عضویت در راز کیهان
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
  const a = getBySlug(slug);
  if (!a) {
    // placeholder page while the first real analysis batch has not landed
    if (analyses.length === 0) return { title: "تحلیل‌ها — به‌زودی", robots: { index: false, follow: true } };
    return {};
  }
  const title = a.target
    ? `تحلیل دادهٔ JWST — ${a.target}`
    : `تحلیل دادهٔ جیمز وب — ${a.product}`;
  const desc =
    (a.text_fa || a.text_en || "").slice(0, 155) ||
    `تحلیل هوش مصنوعی راز کیهان از دادهٔ خام ${a.product} رصدشده با دوربین ${instrumentFa(a.instrument)} تلسکوپ جیمز وب.`;
  return {
    title,
    description: desc,
    alternates: { canonical: `/post/${a.slug}` },
    openGraph: {
      type: "article",
      title: `${title} | راز کیهان`,
      description: desc,
      url: `${SITE_URL}/post/${a.slug}`,
      images: [{ url: a.image || "/og-default.jpg" }],
    },
  };
}

export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const a = getBySlug(slug);
  if (!a) {
    if (analyses.length === 0) return <EmptyAnalyses />;
    notFound();
  }

  const razChan = siteChannels.find((c) => c.id === "fa_ai");
  const title = a.target
    ? `تحلیل دادهٔ JWST — ${a.target}`
    : `تحلیل دادهٔ جیمز وب — ${a.product}`;
  const body = (a.text_fa || a.text_en || "").trim();

  const articleLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: title,
    inLanguage: "fa-IR",
    datePublished: a.published_utc || undefined,
    image: a.image ? SITE_URL + a.image : SITE_URL + "/og-default.jpg",
    author: { "@type": "Organization", name: "راز کیهان (نبض کیهان)", url: SITE_URL },
    publisher: { "@type": "Organization", name: "نبض کیهان", url: SITE_URL },
    about: {
      "@type": "Thing",
      name: a.target || a.product,
      description: `دادهٔ ${a.instrument || "JWST"} — رصد ${a.obs_date || "نامشخص"}`,
    },
  };

  const pUrl = proposalUrl(a.proposal);
  const metaRows: [string, string][] = [
    ["محصول داده", a.product],
    ["هدف رصد", a.target || "—"],
    ["ابزار", instrumentFa(a.instrument) || "—"],
    ["آشکارساز", a.detector || "—"],
    ["فیلتر", a.filter || "—"],
    ["تاریخ رصد", a.obs_date || "—"],
    ["پیشنهاد (Proposal)", a.proposal || "—"],
    ["نوبت انتشار", a.published_utc ? faDateTime(a.published_utc) : "—"],
  ];

  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-4xl px-4 pb-24 pt-28">
        <nav className="mb-6 text-xs text-muted" aria-label="مسیر">
          <Link href="/" className="hover:text-star">خانه</Link>
          <span className="mx-2">/</span>
          <Link href="/#tazeha" className="hover:text-star">تحلیل‌ها</Link>
        </nav>

        <h1 className="mb-4 text-2xl font-black leading-relaxed sm:text-4xl sm:leading-relaxed">{title}</h1>
        <div className="mb-8 flex flex-wrap items-center gap-3 text-xs text-muted">
          <span className="rounded-full bg-nebula/15 px-3 py-1 text-nebula">راز کیهان · تحلیل هوش مصنوعی</span>
          {a.published_utc && <span className="num-fa">{faDateTime(a.published_utc)}</span>}
          {a.quality_score != null && <span className="num-fa">کیفیت داده: {Math.round(a.quality_score).toLocaleString("fa-IR")}</span>}
        </div>

        {a.image && (
          <figure className="mb-8 overflow-hidden rounded-2xl border border-line">
            <img src={a.image} alt={`تصویر پیش‌نمایش ${title}`} className="w-full" />
            <figcaption className="bg-panel/60 px-4 py-2 text-center text-[11px] text-muted">
              پیش‌نمایش دادهٔ خام JWST — {a.product} (اعتبار: NASA / ESA / CSA · STScI)
            </figcaption>
          </figure>
        )}

        {body ? (
          <article className="article-body mb-10">
            {body.split(/\n{2,}|\n/).map((p, i) =>
              p.trim() ? <p key={i}>{p}</p> : null
            )}
          </article>
        ) : (
          <p className="card-cosmic mb-10 p-5 text-sm leading-8 text-muted">
            متن کامل این تحلیل به‌زودی در سایت منتشر می‌شود؛ نسخهٔ کامل آن هم‌اکنون در کانال
            تلگرام «راز کیهان» در دسترس است.
          </p>
        )}

        {/* metadata table */}
        <section className="mb-10" aria-label="مشخصات فنی داده">
          <h2 className="sec-title mb-4 text-xl">مشخصات فنی داده<span className="bar" /></h2>
          <div className="card-cosmic overflow-hidden">
            <table className="w-full text-sm">
              <tbody>
                {metaRows.map(([k, v]) => (
                  <tr key={k} className="border-b border-line/50 last:border-0">
                    <th scope="row" className="w-44 bg-panel/40 px-4 py-3 text-right font-bold text-ink/90">{k}</th>
                    <td className="px-4 py-3 text-muted" dir={/^[a-zA-Z0-9_.\-+ ]+$/.test(v) ? "ltr" : undefined} style={{ textAlign: "start" }}>
                      {k === "پیشنهاد (Proposal)" && pUrl ? (
                        <a href={pUrl} target="_blank" rel="noopener noreferrer" className="text-star hover:underline" dir="ltr">
                          {v} ↗
                        </a>
                      ) : (
                        v
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* CTA */}
        <div className="card-cosmic flex flex-col items-center gap-3 p-8 text-center">
          <p className="text-sm leading-7 text-muted">
            تحلیل‌های بیشتر از دل داده‌های خام جیمز وب، هر روز در کانال «راز کیهان»
          </p>
          <a
            href={`https://t.me/${razChan?.handle || "RazKeyhan"}`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-cosmic btn-primary"
          >
            عضویت در راز کیهان
          </a>
        </div>
      </main>
      <SiteFooter />
      <TelegramFab />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleLd) }} />
    </>
  );
}
