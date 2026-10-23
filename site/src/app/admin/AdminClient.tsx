"use client";

import { useState } from "react";

/**
 * Owner-only placeholder panel. Zero functionality by design (phase 1).
 * Credentials are checked client-side only — nothing sensitive lives behind
 * this gate yet; when real features arrive, this moves behind server auth.
 */
export default function AdminClient() {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState("");
  const [authed, setAuthed] = useState(false);

  if (authed) {
    return (
      <main className="grid min-h-screen place-items-center px-4">
        <div className="card-cosmic w-full max-w-md p-8 text-center">
          <p className="mb-2 text-3xl">🛰️</p>
          <h1 className="mb-2 text-xl font-black">پنل مدیریت — نسخهٔ ۰.۱</h1>
          <p className="text-sm leading-7 text-muted">
            ورود موفق بود. این پنل فعلاً هیچ قابلیتی ندارد؛ امکانات به‌مرور و طبق برنامه
            اضافه می‌شوند.
          </p>
          <button
            onClick={() => setAuthed(false)}
            className="btn-cosmic btn-ghost mt-6 text-sm"
          >
            خروج
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <form
        className="card-cosmic w-full max-w-sm p-8"
        onSubmit={(e) => {
          e.preventDefault();
          if (user === "ROOT_1024" && pass === "ROOT_1024") {
            setError("");
            setAuthed(true);
          } else {
            setError("نام کاربری یا گذرواژه نادرست است.");
          }
        }}
      >
        <h1 className="mb-1 text-center text-lg font-black">ورود</h1>
        <p className="mb-6 text-center text-xs text-muted">دسترسی محدود</p>

        <label className="mb-1 block text-xs text-muted" htmlFor="nk-u">نام کاربری</label>
        <input
          id="nk-u"
          dir="ltr"
          autoComplete="off"
          value={user}
          onChange={(e) => setUser(e.target.value)}
          className="mb-4 w-full rounded-xl border border-line bg-void/70 px-4 py-2.5 text-sm outline-none transition-colors focus:border-star/70"
        />

        <label className="mb-1 block text-xs text-muted" htmlFor="nk-p">گذرواژه</label>
        <input
          id="nk-p"
          dir="ltr"
          type="password"
          autoComplete="off"
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          className="mb-4 w-full rounded-xl border border-line bg-void/70 px-4 py-2.5 text-sm outline-none transition-colors focus:border-star/70"
        />

        {error && <p className="mb-3 text-center text-xs text-red-400">{error}</p>}

        <button type="submit" className="btn-cosmic btn-primary w-full justify-center text-sm">
          ورود
        </button>
      </form>
    </main>
  );
}
