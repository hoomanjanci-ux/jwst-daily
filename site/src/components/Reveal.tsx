"use client";

import { useEffect, useRef } from "react";

/**
 * Fade-in on scroll wrapper — robust for elements of ANY height.
 *
 * Bug fix (owner report 2026-10-24: «خبرها روی موبایل لود نمی‌شوند»):
 * the old observer used `threshold: 0.12`, which requires 12% of the
 * element to be visible. The mobile feed grid is ~12,000 px tall, so on a
 * phone the maximum possible visible ratio is ~7% → the callback never
 * fired → the whole news/analysis grid stayed opacity:0 forever on mobile
 * (desktop worked because its 3-column grid is short enough to cross 12%).
 *
 * Fix: threshold 0 (any visible pixel counts) + a small negative bottom
 * rootMargin so the fade-in still triggers right as the element enters.
 * Works for a 100 px card and a 12,000 px grid alike.
 */
export default function Reveal({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Very old browsers without IntersectionObserver → show immediately.
    if (typeof IntersectionObserver === "undefined") {
      el.classList.add("in");
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        });
      },
      // threshold 0 + -6% bottom margin: fires the moment the element's
      // top enters ~94% of the viewport — same visual timing as before on
      // desktop, and guaranteed to fire on phones for tall grids.
      { threshold: 0, rootMargin: "0px 0px -6% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={ref} className={`reveal ${className}`}>
      {children}
    </div>
  );
}
