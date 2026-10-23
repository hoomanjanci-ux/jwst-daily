"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

/**
 * SiteHeader — desktop nav + mobile hamburger drawer (owner 2026-10-24).
 * Drawer items are exactly what the owner asked for:
 *   content filters: همه / تحلیل‌ها / اخبار  → feed tabs
 *   channels: راز کیهان / نبض کیهان         → Telegram
 *   pages: خانه / چرخش واقعی منظومه
 */
export default function SiteHeader() {
  const [open, setOpen] = useState(false);

  // lock body scroll while the drawer is open
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  // close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const close = () => setOpen(false);

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50 border-b border-line/60 bg-void/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2.5" aria-label="نبض کیهان — صفحهٔ اصلی">
            <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-star/30 to-nebula/30 text-lg">
              ✦
            </span>
            <span className="text-lg font-black tracking-tight">نبض کیهان</span>
          </Link>

          {/* desktop nav — 4th tab: real-time solar system */}
          <nav className="hidden items-center gap-6 text-sm text-muted md:flex">
            <Link href="/" className="transition-colors hover:text-ink">خانه</Link>
            <Link href="/#tazeha" className="transition-colors hover:text-ink">تازه‌ها</Link>
            <Link href="/solar-real" className="transition-colors hover:text-ink">چرخش واقعی منظومه</Link>
            <Link href="/#channels" className="transition-colors hover:text-ink">کانال‌های ما</Link>
          </nav>

          <div className="flex items-center gap-2">
            <a
              href="https://t.me/NabzeKeyhan1"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-cosmic btn-primary !px-4 !py-2 text-xs sm:text-sm"
              title="کانال‌های ما در تلگرام: نبض کیهان، راز کیهان و دو کانال انگلیسی"
            >
              <svg viewBox="0 0 24 24" className="size-4 fill-current" aria-hidden="true">
                <path d="M21.9 4.6c.2-1-.7-1.8-1.6-1.4L2.7 10.1c-1 .4-1 1.9.1 2.2l4.4 1.4 1.7 5.4c.3.9 1.4 1.1 2 .4l2.5-2.6 4.5 3.3c.8.6 2 .1 2.2-.9l1.8-14.7zM8.8 13.2l8.6-5.3c.4-.2.8.3.4.6l-7 6.4-.3 3-1.7-4.7z"/>
              </svg>
              <span className="hidden sm:inline">تلگرام</span>
            </a>

            {/* hamburger — mobile only */}
            <button
              onClick={() => setOpen(true)}
              aria-label="باز کردن منو"
              aria-expanded={open}
              className="grid size-10 place-items-center rounded-xl border border-line/80 bg-panel/50 text-ink transition-colors hover:border-star/50 md:hidden"
            >
              <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* mobile drawer */}
      <div
        className="drawer-backdrop md:hidden"
        data-open={open}
        onClick={close}
        aria-hidden="true"
      />
      <aside
        className="drawer-panel md:hidden"
        data-open={open}
        role="dialog"
        aria-modal="true"
        aria-label="منوی اصلی"
      >
        <div className="flex h-16 items-center justify-between border-b border-line/60 px-4">
          <span className="flex items-center gap-2 text-base font-black">
            <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-star/30 to-nebula/30 text-sm">✦</span>
            منو
          </span>
          <button
            onClick={close}
            aria-label="بستن منو"
            className="grid size-9 place-items-center rounded-lg border border-line/80 text-muted transition-colors hover:text-ink"
          >
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <nav className="flex flex-col gap-1 overflow-y-auto p-3 pb-10">
          <Link href="/" onClick={close} className="drawer-link">
            <span className="text-lg">🏠</span> خانه
          </Link>

          <p className="drawer-group">محتوا</p>
          <Link href="/?tab=all#tazeha" onClick={close} className="drawer-link">
            <span className="text-lg">✨</span> همه
          </Link>
          <Link href="/?tab=analysis#tazeha" onClick={close} className="drawer-link">
            <span className="text-lg">🔭</span> تحلیل‌ها
          </Link>
          <Link href="/?tab=news#tazeha" onClick={close} className="drawer-link">
            <span className="text-lg">📰</span> اخبار
          </Link>

          <p className="drawer-group">کانال‌های تلگرام</p>
          <a
            href="https://t.me/RazKeyhan"
            target="_blank"
            rel="noopener noreferrer"
            onClick={close}
            className="drawer-link"
          >
            <span className="text-lg">🌌</span> راز کیهان
            <span className="mr-auto text-[11px] font-normal text-muted" dir="ltr">@RazKeyhan</span>
          </a>
          <a
            href="https://t.me/NabzeKeyhan1"
            target="_blank"
            rel="noopener noreferrer"
            onClick={close}
            className="drawer-link"
          >
            <span className="text-lg">🛰</span> نبض کیهان
            <span className="mr-auto text-[11px] font-normal text-muted" dir="ltr">@NabzeKeyhan1</span>
          </a>

          <p className="drawer-group">صفحه‌ها</p>
          <Link href="/solar-real" onClick={close} className="drawer-link">
            <span className="text-lg">🌍</span> چرخش واقعی منظومه
          </Link>
          <Link href="/#channels" onClick={close} className="drawer-link">
            <span className="text-lg">📡</span> کانال‌های ما
          </Link>
        </nav>
      </aside>
    </>
  );
}
