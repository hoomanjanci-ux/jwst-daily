import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import HeroIntro from "@/components/HeroIntro";
import Feed from "@/components/Feed";
import Reveal from "@/components/Reveal";
import TelegramFab from "@/components/TelegramFab";
import SolarSystemLazy from "@/components/SolarSystemLazy";
import { siteChannels } from "@/lib/content";

// The 3D scene loads after first paint via the client bridge below —
// LCP stays text-fast (SEO commitment).

export default function HomePage() {
  const faChans = siteChannels.filter((c) => c.lang === "fa");

  return (
    <>
      <SiteHeader />

      <main>
        {/* ================= HERO + 3D SOLAR SYSTEM ================= */}
        <section className="relative flex min-h-[100svh] flex-col overflow-hidden" aria-label="معرفی">
          {/* 3D canvas fills the hero — cinematic animation mode (owner 2026-10-24):
              pure beautiful motion, pauses while the user is rotating it */}
          <div className="absolute inset-0">
            <SolarSystemLazy mode="cinematic" />
          </div>
          {/* readability gradients */}
          <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-void/90 to-transparent" />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-44 bg-gradient-to-t from-void to-transparent" />

          {/* link to the real-time mode (the accurate tab lives on its own page) */}
          <Link
            href="/solar-real"
            className="hud-pill absolute bottom-20 left-1/2 z-10 -translate-x-1/2 px-4 py-1.5 text-[11px] text-muted transition-colors hover:text-ink sm:bottom-6 sm:left-6 sm:translate-x-0"
          >
            🌍 چرخش منظومهٔ شمسی در حالت واقعی ←
          </Link>

          {/* hero copy — typed title + typed white subtitle (owner 2026-10-24) */}
          <div className="relative z-10 mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center px-4 pt-28 text-center">
            <HeroIntro />
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <a href="#tazeha" className="btn-cosmic btn-primary">
                تازه‌های کیهان ↓
              </a>
              <a
                href={`https://t.me/${faChans[0]?.handle || "NabzeKeyhan1"}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-cosmic btn-ghost"
              >
                دنبال کردن در تلگرام
              </a>
            </div>
          </div>

          {/* scroll cue */}
          <div className="relative z-10 pb-6 text-center">
            <span className="inline-block animate-bounce text-2xl text-star/70" aria-hidden="true">⌄</span>
          </div>
        </section>

        {/* ================= FEED (YouTube-style) ================= */}
        <section id="tazeha" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20" aria-label="تازه‌های کیهان">
          <Reveal>
            <h2 className="sec-title mb-2 text-3xl sm:text-4xl">
              تازه‌های کیهان<span className="bar" />
            </h2>
            <p className="mb-10 max-w-2xl text-sm leading-7 text-muted">
              تحلیل‌های هوش مصنوعی «راز کیهان» از داده‌های خام جیمز وب و آخرین اخبار رسمی
              «نبض کیهان» از ناسا و اسا — همه در یک جا.
            </p>
          </Reveal>
          <Reveal>
            <Feed />
          </Reveal>
        </section>

        {/* ================= CHANNELS ================= */}
        <section id="channels" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-24" aria-label="کانال‌های تلگرام">
          <Reveal>
            <h2 className="sec-title mb-2 text-3xl sm:text-4xl">
              کانال‌های ما<span className="bar" />
            </h2>
            <p className="mb-10 max-w-2xl text-sm leading-7 text-muted">
              اخبار رسمی فضا در «نبض کیهان» و تحلیل داده‌های جیمز وب در «راز کیهان».
            </p>
          </Reveal>

          <div className="grid gap-5 sm:grid-cols-2">
            {faChans.map((c) => (
              <Reveal key={c.id}>
                <a
                  href={`https://t.me/${c.handle}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="card-cosmic group flex h-full items-start gap-4 p-6"
                >
                  <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#2fa8df]/25 to-[#2fa8df]/10 text-2xl">
                    ✈️
                  </span>
                  <div>
                    <h3 className="mb-1 flex items-center gap-2 text-lg font-black">
                      {c.name}
                      <span className="text-xs font-normal text-muted" dir="ltr">@{c.handle}</span>
                    </h3>
                    <p className="text-sm leading-7 text-muted">{c.desc}</p>
                    <span className="mt-2 inline-block text-sm font-bold text-star opacity-0 transition-all duration-300 group-hover:opacity-100">
                      عضویت در کانال ←
                    </span>
                  </div>
                </a>
              </Reveal>
            ))}
          </div>


        </section>
      </main>

      <SiteFooter />
      <TelegramFab />
    </>
  );
}
