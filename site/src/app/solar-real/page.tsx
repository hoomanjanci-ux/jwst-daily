import type { Metadata } from "next";
import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import TelegramFab from "@/components/TelegramFab";
import SolarSystemLazy from "@/components/SolarSystemLazy";

const TITLE = "چرخش منظومهٔ شمسی در حالت واقعی";
const DESC =
  "منظومهٔ شمسی سه‌بعدی، زنده و هم‌گام با زمان واقعی؛ همین حالا زمین دقیقاً همان‌جایی است که در واقعیت قرار دارد.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESC,
  alternates: { canonical: "/solar-real" },
  openGraph: {
    type: "website",
    title: `${TITLE} | نبض کیهان`,
    description: DESC,
    url: "https://nabzekeyhan.ir/solar-real",
    images: [{ url: "/og-default.jpg", width: 1200, height: 630, alt: TITLE }],
  },
};

export default function SolarRealPage() {
  return (
    <>
      <SiteHeader />
      <main>
        <section
          className="relative flex min-h-[100svh] flex-col overflow-hidden"
          aria-label={TITLE}
        >
          {/* 3D canvas — REAL-TIME mode: wall-clock synced, accurate positions */}
          <div className="absolute inset-0">
            <SolarSystemLazy mode="real" />
          </div>
          <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-void/90 to-transparent" />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-44 bg-gradient-to-t from-void to-transparent" />

          {/* copy */}
          <div className="relative z-10 mx-auto w-full max-w-3xl px-4 pt-24 text-center">
            <h1 className="text-2xl font-black leading-relaxed text-ink sm:text-4xl sm:leading-relaxed">
              {TITLE}
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-muted sm:text-base sm:leading-8">
              منظومهٔ شمسی زیر همین متن، زنده و هم‌گام با زمان واقعی است؛ همین حالا زمین دقیقاً
              همان‌جایی می‌چرخد که در واقعیت است. جای سیاره‌ها روی مدارشان، چرخش شبانه‌روزی زمین،
              کجی محور آن و موقعیت ماه، همگی از زمان واقعی محاسبه می‌شوند.
            </p>
            <p className="mx-auto mt-2 max-w-2xl text-xs leading-6 text-muted/80 sm:text-sm">
              برای نگاه از زاویهٔ دیگر، صحنه را بچرخانید؛ با اسکرول یا پینچ نزدیک و دور کنید و با
              دکمه‌های سرعت زمان، گذر ساعت‌ها و ماه‌ها را تماشا کنید.
            </p>
          </div>

          {/* back link */}
          <div className="relative z-10 pb-6 text-center">
            <Link href="/" className="hud-pill inline-block px-4 py-1.5 text-xs text-muted transition-colors hover:text-ink">
              ← بازگشت به صفحهٔ اصلی
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
      <TelegramFab />
    </>
  );
}
