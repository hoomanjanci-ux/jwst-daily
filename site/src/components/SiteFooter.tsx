import Link from "next/link";
import { siteChannels } from "@/lib/content";

export default function SiteFooter() {
  return (
    <footer className="border-t border-line/60 bg-deep/60">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-10 md:grid-cols-3">
          {/* brand */}
          <div>
            <div className="mb-3 flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-star/30 to-nebula/30">✦</span>
              <span className="text-lg font-black">نبض کیهان</span>
            </div>
            <p className="text-sm leading-7 text-muted">
              نبض کیهان و راز کیهان — اخبار رسمی فضا و تحلیل داده‌های خام تلسکوپ جیمز وب،
              به فارسی و انگلیسی؛ همه‌چیز خودکار، شفاف و با ذکر منبع.
            </p>
          </div>

          {/* channels */}
          <div>
            <h3 className="mb-4 font-bold">کانال‌های تلگرام</h3>
            <ul className="space-y-2.5 text-sm">
              {siteChannels.map((c) => (
                <li key={c.id}>
                  <a
                    href={`https://t.me/${c.handle}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center gap-2 text-muted transition-colors hover:text-star"
                  >
                    <span className="size-1.5 rounded-full bg-star/60 transition group-hover:bg-star" />
                    {c.name}
                    <span className="text-xs opacity-60" dir="ltr">@{c.handle}</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* links */}
          <div>
            <h3 className="mb-4 font-bold">لینک‌ها</h3>
            <ul className="space-y-2.5 text-sm text-muted">
              <li><Link href="/#tazeha" className="transition-colors hover:text-ink">تازه‌های کیهان</Link></li>
              <li><Link href="/#channels" className="transition-colors hover:text-ink">دربارهٔ کانال‌ها</Link></li>
              <li>
                <a
                  href="https://webbtelescope.org"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="transition-colors hover:text-ink"
                >
                  وب‌سایت رسمی تلسکوپ جیمز وب
                </a>
              </li>
              <li>
                <a
                  href="https://www.nasa.gov/webb"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="transition-colors hover:text-ink"
                >
                  صفحهٔ JWST در ناسا
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="ticker-line my-8" />

        <div className="flex flex-col items-center justify-between gap-3 text-xs text-muted sm:flex-row">
          <p>© {new Intl.DateTimeFormat("fa-IR", { year: "numeric", timeZone: "Asia/Tehran" }).format(new Date())} نبض کیهان</p>
          <p>تصاویر: NASA / ESA / CSA · تحلیل‌ها توسط هوش مصنوعی تولید و با ذکر منبع منتشر می‌شوند</p>
        </div>
      </div>
    </footer>
  );
}
