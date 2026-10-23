import Link from "next/link";
import { siteChannels } from "@/lib/content";

export default function SiteHeader() {
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-line/60 bg-void/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2.5" aria-label="نبض کیهان — صفحهٔ اصلی">
          <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-star/30 to-nebula/30 text-lg">
            ✦
          </span>
          <span className="text-lg font-black tracking-tight">نبض کیهان</span>
        </Link>

        <nav className="hidden items-center gap-6 text-sm text-muted sm:flex">
          <Link href="/" className="transition-colors hover:text-ink">خانه</Link>
          <Link href="/#tazeha" className="transition-colors hover:text-ink">تازه‌ها</Link>
          <Link href="/#channels" className="transition-colors hover:text-ink">کانال‌های ما</Link>
        </nav>

        <div className="flex items-center gap-2">
          {siteChannels.filter((c) => c.lang === "fa").map((c) => (
            <a
              key={c.id}
              href={`https://t.me/${c.handle}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-cosmic btn-primary !px-4 !py-2 text-xs sm:text-sm"
              title={c.desc}
            >
              <svg viewBox="0 0 24 24" className="size-4 fill-current" aria-hidden="true">
                <path d="M21.9 4.6c.2-1-.7-1.8-1.6-1.4L2.7 10.1c-1 .4-1 1.9.1 2.2l4.4 1.4 1.7 5.4c.3.9 1.4 1.1 2 .4l2.5-2.6 4.5 3.3c.8.6 2 .1 2.2-.9l1.8-14.7zM8.8 13.2l8.6-5.3c.4-.2.8.3.4.6l-7 6.4-.3 3-1.7-4.7z"/>
              </svg>
              تلگرام
            </a>
          ))}
        </div>
      </div>
    </header>
  );
}
