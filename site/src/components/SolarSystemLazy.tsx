"use client";

import dynamic from "next/dynamic";

/**
 * Client bridge: Next 16 forbids `ssr:false` dynamic imports from Server
 * Components, so the hero mounts this client component which in turn lazily
 * loads the WebGL scene (kept off the server bundle, fast text-first LCP).
 */
const SolarSystem = dynamic(() => import("./SolarSystem"), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 bg-[radial-gradient(70%_70%_at_50%_55%,#0c1738,#04060f)]">
      <div className="absolute inset-0 opacity-40 [background-image:radial-gradient(1px_1px_at_20%_30%,#fff_50%,transparent_50%),radial-gradient(1px_1px_at_60%_70%,#cfe0ff_50%,transparent_50%),radial-gradient(1.5px_1.5px_at_80%_25%,#fff_50%,transparent_50%),radial-gradient(1px_1px_at_35%_80%,#ffe9c9_50%,transparent_50%)] [background-size:220px_220px]" />
      <div className="absolute inset-0 grid place-items-center">
        <span className="text-xs text-muted">در حال آماده‌سازی منظومهٔ شمسی…</span>
      </div>
    </div>
  ),
});

export default function SolarSystemLazy() {
  return <SolarSystem />;
}
