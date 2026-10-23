"use client";

import { useRef, useCallback } from "react";

/**
 * HeroTitle — CSS-3D animated site title with pointer tilt.
 * Real 3D feel: perspective + preserve-3d + layered drop-shadows + float.
 */
export default function HeroTitle() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLHeadingElement>(null);

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

  return (
    <div
      ref={wrapRef}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className="hero-3d-wrap select-none px-4 text-center"
    >
      <h1
        ref={textRef}
        className="hero-3d mx-auto inline-block text-6xl font-black leading-tight sm:text-7xl lg:text-8xl"
      >
        نبض کیهان
      </h1>
    </div>
  );
}
