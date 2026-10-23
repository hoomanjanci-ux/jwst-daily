"use client";

import { useEffect, useState } from "react";

/** Floating Telegram button — cross-promotion to the Persian channel. */
export default function TelegramFab() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 420);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <a
      href="https://t.me/NabzeKeyhan1"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="کانال نبض کیهان در تلگرام"
      className={`fixed bottom-5 right-5 z-50 grid size-14 place-items-center rounded-full bg-gradient-to-br from-[#2fa8df] to-[#1d7fb8] text-white shadow-[0_10px_34px_rgba(47,168,223,0.45)] transition-all duration-300 hover:scale-110 ${
        show ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-6 opacity-0"
      }`}
    >
      <svg viewBox="0 0 24 24" className="size-7 fill-current" aria-hidden="true">
        <path d="M21.9 4.6c.2-1-.7-1.8-1.6-1.4L2.7 10.1c-1 .4-1 1.9.1 2.2l4.4 1.4 1.7 5.4c.3.9 1.4 1.1 2 .4l2.5-2.6 4.5 3.3c.8.6 2 .1 2.2-.9l1.8-14.7zM8.8 13.2l8.6-5.3c.4-.2.8.3.4.6l-7 6.4-.3 3-1.7-4.7z"/>
      </svg>
    </a>
  );
}
