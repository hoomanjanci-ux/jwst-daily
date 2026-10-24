"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * HeroIntro — typed hero (owner request 2026-10-24):
 * «متن نبض کیهان که روی منظومهٔ شمسی است، با متن سفید ریز زیرش، باید
 *  تایپ‌شدن داشته باشد» — on BOTH mobile and desktop.
 *
 * How it works (deliberately boring engineering for a fragile spot):
 * - The FULL title and subtitle are always in the DOM: an invisible copy
 *   reserves the exact final space (zero layout shift while typing) and
 *   keeps the real text in the static HTML for SEO/crawlers.
 * - A second, absolutely-positioned copy is typed into a SINGLE text node
 *   (never per-character spans — spans would break Persian letter joining,
 *   e.g. نبض کیهان would render as isolated letters).
 * - Title types first, short beat, then the small white subtitle types.
 * - A soft caret rides the writing head and retires when done.
 * - prefers-reduced-motion → both lines appear instantly.
 * - The desktop 3D mouse tilt is preserved exactly as it was.
 */

const TITLE = "نبض کیهان";
const SUBTITLE =
  "اخبار رسمی فضا، تحلیل نجومی، داده‌های خام تلسکوپ جیمز، به زبان فارسی.";

const TITLE_CHARS = Array.from(TITLE);
const SUB_CHARS = Array.from(SUBTITLE);

export default function HeroIntro() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLHeadingElement>(null);

  const [tCount, setTCount] = useState(0);
  const [sCount, setSCount] = useState(0);
  const [started, setStarted] = useState(false);
  const [titleDone, setTitleDone] = useState(false);
  const [allDone, setAllDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

    (async () => {
      const reduced =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      if (reduced) {
        setTCount(TITLE_CHARS.length);
        setSCount(SUB_CHARS.length);
        setStarted(true);
        setTitleDone(true);
        setAllDone(true);
        return;
      }

      // small beat so the solar system starts fading in first
      await wait(600);
      if (cancelled) return;
      setStarted(true);

      for (let i = 1; i <= TITLE_CHARS.length; i++) {
        if (cancelled) return;
        setTCount(i);
        await wait(TITLE_CHARS[i - 1] === " " ? 110 : 155);
      }
      if (cancelled) return;
      setTitleDone(true);

      await wait(380);
      if (cancelled) return;

      for (let i = 1; i <= SUB_CHARS.length; i++) {
        if (cancelled) return;
        setSCount(i);
        const ch = SUB_CHARS[i - 1];
        await wait(ch === "،" ? 240 : ch === " " ? 60 : 27);
      }
      if (cancelled) return;

      // let the caret blink on the finished line for a moment, then retire it
      await wait(1600);
      if (cancelled) return;
      setAllDone(true);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // Desktop 3D tilt — same behaviour as the previous HeroTitle component.
  const onMove = useCallback((e: React.MouseEvent) => {
    const wrap = wrapRef.current;
    const el = textRef.current;
    if (!wrap || !el) return;
    const r = wrap.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `rotateX(${(-py * 14).toFixed(2)}deg) rotateY(${(px * 18).toFixed(2)}deg)`;
  }, []);

  const onLeave = useCallback(() => {
    if (textRef.current) textRef.current.style.transform = "rotateX(0deg) rotateY(0deg)";
  }, []);

  const typedTitle = TITLE_CHARS.slice(0, tCount).join("");
  const typedSub = SUB_CHARS.slice(0, sCount).join("");

  return (
    <>
      <div
        ref={wrapRef}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
        className="hero-3d-wrap select-none px-4 text-center"
      >
        <h1
          ref={textRef}
          aria-label={TITLE}
          className="hero-float mx-auto inline-block text-6xl font-black leading-tight sm:text-7xl lg:text-8xl"
        >
          {/* invisible copy = exact space reservation (no layout shift) */}
          <span className="relative inline-block">
            <span className="hero-3d invisible" aria-hidden="true">
              {TITLE}
            </span>
            {/* typed copy rides on top, single text node keeps shaping correct */}
            <span className="hero-3d absolute inset-0" aria-hidden="true">
              {typedTitle}
              {started && !titleDone && <span className="tw-caret" />}
            </span>
          </span>
        </h1>
      </div>

      <p
        aria-label={SUBTITLE}
        className="mt-7 max-w-2xl text-base leading-8 text-ink/90 sm:text-lg"
      >
        <span className="relative block">
          <span aria-hidden="true" className="invisible">
            {SUBTITLE}
          </span>
          <span aria-hidden="true" className="absolute inset-0">
            {typedSub}
            {titleDone && !allDone && <span className="tw-caret" />}
          </span>
        </span>
      </p>
    </>
  );
}
