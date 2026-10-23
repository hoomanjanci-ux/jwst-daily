"use client";

import { useEffect, useRef, useState, useCallback } from "react";

/**
 * SolarSystem — real 3D solar system (three.js), Persian labels.
 *
 * Reality sync (the owner's core requirement):
 *  - Earth spin/orientation: subsolar-meridian construction
 *      α = L_earth + π + 2π·(UTC hours / 24)
 *    where L_earth = mean ecliptic longitude (J2000, 0.98560910°/day).
 *    This yields the true sidereal rotation rate (360.9856°/day) AND puts
 *    the correct hemisphere toward the Sun for the current UTC moment.
 *  - Earth/Mars/Jupiter/Saturn orbital angle = J2000 mean longitudes
 *    (correct mean position along the orbit for today's date).
 *  - Moon: mean longitude (13.176396°/day).
 *  - Axial tilts: Earth -23.44° (phase-aligned so northern summer lands at
 *    L≈270°), Saturn 26.7°, Moon orbit inclination 5.14°.
 *  - "واقعی" mode = wall-clock time. Warp modes fast-forward the same model.
 */

type Speed = 1 | 3600 | 43200;
import type * as ThreeNS from "three";

const J2000 = 946728000000; // 2000-01-01T12:00Z
const D2R = Math.PI / 180;

// J2000 mean longitudes (deg) and daily motion (deg/day)
const LON = {
  earth: { l0: 100.46435, n: 0.9856091 },
  mars: { l0: 355.433, n: 0.52402068 },
  jupiter: { l0: 34.35151, n: 0.0830853 },
  saturn: { l0: 50.077471, n: 0.03344423 },
  moon: { l0: 218.316, n: 13.176396 },
};

const deg = (l0: number, n: number, d: number) =>
  ((l0 + n * d) % 360) * D2R;

function makeLabel(text: string): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 96;
  const ctx = c.getContext("2d")!;
  ctx.font = "600 44px Vazirmatn, Tahoma, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = "rgba(4,6,15,0.95)";
  ctx.shadowBlur = 12;
  ctx.fillStyle = "rgba(233,238,252,0.92)";
  ctx.fillText(text, 128, 50);
  return c;
}

function bodyTexture(base: string, bands: string[], spots?: { x: number; y: number; r: number; c: string }[]): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 128;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 256, 128);
  bands.forEach((col, i) => {
    ctx.fillStyle = col;
    const y = (i / bands.length) * 128;
    ctx.globalAlpha = 0.55;
    ctx.fillRect(0, y, 256, 128 / bands.length + 1);
  });
  ctx.globalAlpha = 1;
  for (let i = 0; i < 220; i++) {
    ctx.fillStyle = Math.random() > 0.5 ? "rgba(0,0,0,0.10)" : "rgba(255,255,255,0.06)";
    ctx.beginPath();
    ctx.arc(Math.random() * 256, Math.random() * 128, Math.random() * 5 + 1, 0, Math.PI * 2);
    ctx.fill();
  }
  (spots || []).forEach((s) => {
    ctx.fillStyle = s.c;
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fill();
  });
  return c;
}

function ringTexture(): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 512;
  const ctx = c.getContext("2d")!;
  const img = ctx.createImageData(512, 512);
  for (let y = 0; y < 512; y++) {
    for (let x = 0; x < 512; x++) {
      const dx = x - 256, dy = y - 256;
      const r = Math.sqrt(dx * dx + dy * dy) / 256; // 0..1
      const i = (y * 512 + x) * 4;
      if (r < 0.62 || r > 0.98) { img.data[i + 3] = 0; continue; }
      const band = Math.sin(r * 90) * 0.5 + 0.5;
      const gap = r > 0.78 && r < 0.82 ? 0.15 : 1; // Cassini division
      const a = (band * 0.55 + 0.25) * gap;
      img.data[i] = 210; img.data[i + 1] = 185; img.data[i + 2] = 150;
      img.data[i + 3] = Math.max(0, Math.min(255, a * 255));
    }
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

function glowTexture(inner: string, outer: string): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 256;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, inner);
  g.addColorStop(0.35, outer);
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return c;
}

export default function SolarSystem() {
  const mountRef = useRef<HTMLDivElement>(null);
  const [speed, setSpeed] = useState<Speed>(1);
  const speedRef = useRef<Speed>(1);
  const [failed, setFailed] = useState(false);
  const [clock, setClock] = useState("--:--:--");
  const [hintOn, setHintOn] = useState(true);

  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  // Tehran clock (updates every second)
  useEffect(() => {
    const fmt = new Intl.DateTimeFormat("fa-IR", {
      timeZone: "Asia/Tehran",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    const tick = () => setClock(fmt.format(new Date()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setHintOn(false), 7000);
    return () => clearTimeout(t);
  }, []);

  const setSpeedAndReset = useCallback((s: Speed) => {
    setSpeed(s);
    // request the scene to re-sync to wall-clock when returning to real time
    (window as unknown as { __nkResync?: boolean }).__nkResync = s === 1;
  }, []);

  useEffect(() => {
    let disposed = false;
    const mount = mountRef.current;
    if (!mount) return;

    let renderer: import("three").WebGLRenderer;
    let THREE: typeof import("three");
    let cleanup: (() => void) | null = null;

    (async () => {
      try {
        THREE = await import("three");
        const { OrbitControls } = await import(
          "three/examples/jsm/controls/OrbitControls.js"
        );
        if (disposed) return;

        const isMobile = mount.clientWidth < 768;
        const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(mount.clientWidth, mount.clientHeight);
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.05;
        renderer.domElement.style.display = "block";
        renderer.domElement.style.touchAction = "none";
        mount.appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x030510);

        const camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 0.5, 3000);
        camera.position.set(0, isMobile ? 62 : 52, isMobile ? 165 : 138);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.06;
        controls.enablePan = false;
        controls.minDistance = 26;
        controls.maxDistance = 340;
        controls.rotateSpeed = 0.55;
        controls.zoomSpeed = 0.9;

        // ---------- lights ----------
        scene.add(new THREE.AmbientLight(0x8fa8d8, 0.35));
        const sunLight = new THREE.PointLight(0xfff2d8, 2.6, 0, 0);
        scene.add(sunLight);

        const texLoader = new THREE.TextureLoader();
        const loadTex = (url: string, srgb = true) => {
          const t = texLoader.load(url);
          if (srgb) t.colorSpace = THREE.SRGBColorSpace;
          return t;
        };

        // ---------- starfield ----------
        const mkStars = (count: number, size: number, opacity: number, palette: number[]) => {
          const pos = new Float32Array(count * 3);
          for (let i = 0; i < count; i++) {
            const r = 480 + Math.random() * 520;
            const th = Math.random() * Math.PI * 2;
            const ph = Math.acos(2 * Math.random() - 1);
            pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
            pos[i * 3 + 1] = r * Math.cos(ph);
            pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
          }
          const g = new THREE.BufferGeometry();
          g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
          const m = new THREE.PointsMaterial({
            size,
            color: palette[Math.floor(Math.random() * palette.length)],
            transparent: true,
            opacity,
            sizeAttenuation: true,
          });
          const p = new THREE.Points(g, m);
          scene.add(p);
          return p;
        };
        mkStars(isMobile ? 1400 : 2600, 1.35, 0.85, [0xffffff, 0xdde8ff, 0xcfe0ff]);
        mkStars(isMobile ? 400 : 800, 2.6, 0.7, [0x9fc5ff, 0xf2d9a4, 0xd6b8ff]);

        // ---------- sun ----------
        const sunGroup = new THREE.Group();
        const sunCanvas = document.createElement("canvas");
        sunCanvas.width = 256; sunCanvas.height = 256;
        {
          const ctx = sunCanvas.getContext("2d")!;
          const g = ctx.createRadialGradient(128, 128, 10, 128, 128, 128);
          g.addColorStop(0, "#fffdf4");
          g.addColorStop(0.3, "#ffe9a8");
          g.addColorStop(0.7, "#ffb84d");
          g.addColorStop(1, "#ff8a2a");
          ctx.fillStyle = g;
          ctx.fillRect(0, 0, 256, 256);
        }
        const sunTex = new THREE.CanvasTexture(sunCanvas);
        sunTex.colorSpace = THREE.SRGBColorSpace;
        const sun = new THREE.Mesh(
          new THREE.SphereGeometry(11, isMobile ? 32 : 48, isMobile ? 24 : 32),
          new THREE.MeshBasicMaterial({ map: sunTex })
        );
        sunGroup.add(sun);
        const sunGlow = new THREE.Sprite(
          new THREE.SpriteMaterial({
            map: new THREE.CanvasTexture(glowTexture("rgba(255,236,180,0.95)", "rgba(255,150,40,0.38)")),
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            transparent: true,
          })
        );
        sunGlow.scale.set(72, 72, 1);
        sunGroup.add(sunGlow);
        scene.add(sunGroup);

        // ---------- orbit lines ----------
        const orbitLine = (radius: number, opacity = 0.5) => {
          const pts: number[] = [];
          for (let i = 0; i <= 128; i++) {
            const a = (i / 128) * Math.PI * 2;
            pts.push(Math.cos(a) * radius, 0, -Math.sin(a) * radius);
          }
          const g = new THREE.BufferGeometry();
          g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
          const l = new THREE.Line(
            g,
            new THREE.LineBasicMaterial({ color: 0x2c3f74, transparent: true, opacity })
          );
          scene.add(l);
          return l;
        };
        const R_EARTH = 62, R_MARS = 88, R_JUP = 128, R_SAT = 175;
        orbitLine(R_EARTH, 0.55);
        orbitLine(R_MARS, 0.4);
        orbitLine(R_JUP, 0.32);
        orbitLine(R_SAT, 0.26);

        // ---------- planets ----------
        const labels: ThreeNS.Sprite[] = [];
        const addLabel = (text: string, parent: ThreeNS.Object3D, y: number, scale = 1) => {
          const sp = new THREE.Sprite(
            new THREE.SpriteMaterial({
              map: new THREE.CanvasTexture(makeLabel(text)),
              transparent: true,
              depthWrite: false,
            })
          );
          sp.position.set(0, y, 0);
          sp.scale.set(15 * scale, 5.6 * scale, 1);
          parent.add(sp);
          labels.push(sp);
          return sp;
        };

        const sphere = (r: number, w: number, h: number, mat: ThreeNS.Material) =>
          new THREE.Mesh(new THREE.SphereGeometry(r, w, h), mat);

        // Earth
        const earthOrbit = new THREE.Group();
        scene.add(earthOrbit);
        const earthTilt = new THREE.Group();
        earthTilt.rotation.x = -23.44 * D2R;
        earthOrbit.add(earthTilt);
        const earth = sphere(4.6, isMobile ? 40 : 64, isMobile ? 28 : 48,
          new THREE.MeshPhongMaterial({ map: loadTex("/textures/earth_atmos_2048.jpg"), shininess: 6, specular: new THREE.Color(0x223a5e) }));
        earthTilt.add(earth);
        const clouds = sphere(4.68, isMobile ? 32 : 48, isMobile ? 24 : 32,
          new THREE.MeshLambertMaterial({ map: loadTex("/textures/earth_clouds_1024.png"), transparent: true, opacity: 0.5, depthWrite: false }));
        earthTilt.add(clouds);
        const atmo = sphere(5.15, 32, 24,
          new THREE.MeshBasicMaterial({ color: 0x4d9fff, transparent: true, opacity: 0.14, side: THREE.BackSide, depthWrite: false }));
        earthTilt.add(atmo);
        addLabel("زمین", earthOrbit, 9);

        // Moon
        const moonIncl = new THREE.Group();
        moonIncl.rotation.x = 5.14 * D2R;
        earthOrbit.add(moonIncl);
        const moon = sphere(1.25, 28, 20,
          new THREE.MeshPhongMaterial({ map: loadTex("/textures/moon_1024.jpg"), shininess: 2 }));
        moonIncl.add(moon);
        {
          const pts: number[] = [];
          for (let i = 0; i <= 64; i++) {
            const a = (i / 64) * Math.PI * 2;
            pts.push(Math.cos(a) * 8.6, 0, -Math.sin(a) * 8.6);
          }
          const g = new THREE.BufferGeometry();
          g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
          moonIncl.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x2c3f74, transparent: true, opacity: 0.3 })));
        }
        addLabel("ماه", moonIncl, 3.4, 0.62);

        // Mars
        const marsOrbit = new THREE.Group();
        scene.add(marsOrbit);
        const marsTex = new THREE.CanvasTexture(bodyTexture("#b3552e", ["#c26a3a", "#9c4523", "#cf7b49", "#8f3d1f"], [
          { x: 128, y: 16, r: 9, c: "rgba(240,240,235,0.85)" },
        ]));
        marsTex.colorSpace = THREE.SRGBColorSpace;
        const mars = sphere(3.1, isMobile ? 32 : 48, isMobile ? 24 : 32,
          new THREE.MeshPhongMaterial({ map: marsTex, shininess: 3 }));
        marsOrbit.add(mars);
        addLabel("مریخ", marsOrbit, 6, 0.8);

        // Jupiter
        const jupOrbit = new THREE.Group();
        scene.add(jupOrbit);
        const jupTex = new THREE.CanvasTexture(bodyTexture("#c9a97e", ["#e3c9a0", "#b58a5f", "#d9b98f", "#a3714c", "#e8d3ae", "#b58a5f", "#d9b98f"], [
          { x: 178, y: 84, r: 7, c: "rgba(196,90,58,0.9)" },
        ]));
        jupTex.colorSpace = THREE.SRGBColorSpace;
        const jup = sphere(7.4, isMobile ? 36 : 56, isMobile ? 26 : 40,
          new THREE.MeshPhongMaterial({ map: jupTex, shininess: 4 }));
        jupOrbit.add(jup);
        addLabel("مشتری", jupOrbit, 11.4, 1);

        // Saturn
        const satOrbit = new THREE.Group();
        scene.add(satOrbit);
        const satTilt = new THREE.Group();
        satTilt.rotation.x = 26.7 * D2R;
        satOrbit.add(satTilt);
        const satTex = new THREE.CanvasTexture(bodyTexture("#d8bc8a", ["#e8d5ab", "#c3a374", "#e3cea4", "#cdb186"]));
        satTex.colorSpace = THREE.SRGBColorSpace;
        const sat = sphere(6.2, isMobile ? 36 : 56, isMobile ? 26 : 40,
          new THREE.MeshPhongMaterial({ map: satTex, shininess: 5 }));
        satTilt.add(sat);
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(8.4, 14.4, isMobile ? 48 : 96),
          new THREE.MeshBasicMaterial({
            map: new THREE.CanvasTexture(ringTexture()),
            side: THREE.DoubleSide,
            transparent: true,
            depthWrite: false,
          })
        );
        ring.rotation.x = Math.PI / 2;
        satTilt.add(ring);
        addLabel("زحل", satOrbit, 10.6, 0.95);

        // sharp label rendering
        labels.forEach((l) => {
          const m = l.material as ThreeNS.SpriteMaterial;
          if (m.map) m.map.anisotropy = 4;
        });

        // ---------- simulation loop ----------
        let simMs = Date.now();
        let lastFrame = performance.now();
        let raf = 0;

        const renderLoop = () => {
          raf = requestAnimationFrame(renderLoop);
          const nowPerf = performance.now();
          const dt = Math.min(0.1, (nowPerf - lastFrame) / 1000);
          lastFrame = nowPerf;

          const w = window as unknown as { __nkResync?: boolean };
          if (w.__nkResync) {
            simMs = Date.now();
            w.__nkResync = false;
          }
          if (speedRef.current === 1) simMs = Date.now();
          else simMs += dt * speedRef.current * 1000;

          const d = simMs / 86400000 - 10957.5; // days since J2000
          const utcHours = ((simMs / 3600000) % 24 + 24) % 24;

          // Earth: orbit position + true rotation
          const Le = deg(LON.earth.l0, LON.earth.n, d);
          earthOrbit.position.set(Math.cos(Le) * R_EARTH, 0, -Math.sin(Le) * R_EARTH);
          earth.rotation.y = Le + Math.PI + (utcHours / 24) * Math.PI * 2;
          clouds.rotation.y = earth.rotation.y * 1.08;

          // Moon
          const Lm = deg(LON.moon.l0, LON.moon.n, d);
          moon.position.set(Math.cos(Lm) * 8.6, 0, -Math.sin(Lm) * 8.6);

          // Mars / Jupiter / Saturn
          const Lma = deg(LON.mars.l0, LON.mars.n, d);
          marsOrbit.position.set(Math.cos(Lma) * R_MARS, 0, -Math.sin(Lma) * R_MARS);
          mars.rotation.y = Lma + Math.PI + (utcHours / 24.62) * Math.PI * 2;
          const Lj = deg(LON.jupiter.l0, LON.jupiter.n, d);
          jupOrbit.position.set(Math.cos(Lj) * R_JUP, 0, -Math.sin(Lj) * R_JUP);
          jup.rotation.y = Lj + Math.PI + (utcHours / 9.93) * Math.PI * 2;
          const Ls = deg(LON.saturn.l0, LON.saturn.n, d);
          satOrbit.position.set(Math.cos(Ls) * R_SAT, 0, -Math.sin(Ls) * R_SAT);
          sat.rotation.y = Ls + Math.PI + (utcHours / 10.7) * Math.PI * 2;

          // sun spin + subtle breathing
          sun.rotation.y += dt * 0.02;
          if (!reduced) {
            const breathe = 1 + Math.sin(nowPerf / 900) * 0.012;
            sunGlow.scale.set(72 * breathe, 72 * breathe, 1);
          }

          controls.update();
          renderer.render(scene, camera);
        };
        renderLoop();

        // resize
        const ro = new ResizeObserver(() => {
          if (!mount.clientWidth || !mount.clientHeight) return;
          camera.aspect = mount.clientWidth / mount.clientHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(mount.clientWidth, mount.clientHeight);
        });
        ro.observe(mount);

        cleanup = () => {
          cancelAnimationFrame(raf);
          ro.disconnect();
          controls.dispose();
          scene.traverse((obj) => {
            const mesh = obj as import("three").Mesh;
            if (mesh.geometry) mesh.geometry.dispose();
            const mat = (mesh as unknown as { material?: import("three").Material | import("three").Material[] }).material;
            if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
            else if (mat) mat.dispose();
          });
          renderer.dispose();
          if (renderer.domElement.parentElement === mount) mount.removeChild(renderer.domElement);
        };
      } catch (err) {
        console.error("SolarSystem init failed:", err);
        if (!disposed) setFailed(true);
      }
    })();

    return () => {
      disposed = true;
      if (cleanup) cleanup();
    };
  }, []);

  return (
    <div className="relative h-full w-full" dir="rtl">
      <div ref={mountRef} className="absolute inset-0" aria-label="منظومهٔ شمسی سه‌بعدی تعاملی" />

      {failed && (
        <div className="absolute inset-0 flex items-center justify-center bg-[radial-gradient(80%_80%_at_50%_40%,#122043,#04060f)]">
          <p className="text-muted text-sm">نمایش سه‌بعدی در این مرورگر پشتیبانی نمی‌شود.</p>
        </div>
      )}

      {/* top hint */}
      <div
        className={`pointer-events-none absolute inset-x-0 top-3 flex justify-center transition-opacity duration-1000 ${hintOn ? "opacity-100" : "opacity-0"}`}
      >
        <span className="hud-pill px-4 py-1.5 text-xs text-muted">
          بچرخانید • با اسکرول یا پینچ زوم کنید
        </span>
      </div>

      {/* Tehran clock + reality badge */}
      <div className="absolute bottom-3 left-3 flex flex-col items-start gap-1.5">
        <span className="hud-pill px-3 py-1 text-[11px] text-muted">
          ساعت تهران: <span className="num-fa text-ink">{clock}</span>
        </span>
        <span
          className="hud-pill px-3 py-1 text-[11px]"
          style={{ color: speed === 1 ? "#7fe3a8" : "#f2c76e" }}
        >
          {speed === 1 ? "● هم‌گام با زمان واقعی" : `▲ شتاب زمان ×${speed.toLocaleString("fa-IR")}`}
        </span>
      </div>

      {/* speed control */}
      <div className="absolute bottom-3 right-3 flex items-center gap-1 hud-pill p-1">
        <span className="px-2 text-[11px] text-muted">سرعت زمان:</span>
        <button className="hud-btn" data-active={speed === 1} onClick={() => setSpeedAndReset(1)}>واقعی</button>
        <button className="hud-btn" data-active={speed === 3600} onClick={() => setSpeedAndReset(3600)}>سریع</button>
        <button className="hud-btn" data-active={speed === 43200} onClick={() => setSpeedAndReset(43200)}>خیلی سریع</button>
      </div>
    </div>
  );
}
