"use client";

import { useEffect, useRef } from "react";

/**
 * Animated "molecule" background for the sign-in page - floating dots with
 * lines drawn between nearby ones (like the connected-dot network on
 * qualithics.com), rendered on a plain <canvas> rather than a charting/
 * animation library - matches this codebase's existing "plain elements
 * over heavy dependencies" pattern (native <select>, CSS bar charts, etc.
 * - see aboutproject.md). Colors are the brand primary/accent hex values
 * (identical in both :root and .dark in globals.css), so no per-theme
 * palette swap is needed - only line/dot opacity is bumped up a bit in
 * dark mode for visibility against the darker background.
 */

const PRIMARY_RGB = "91, 79, 207"; // --primary #5B4FCF
const ACCENT_RGB = "224, 163, 60"; // --accent #E0A33C
const LINK_DIST = 150;

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  accent: boolean;
}

export function ParticleBackground({ dark }: { dark: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const darkRef = useRef(dark);

  useEffect(() => {
    darkRef.current = dark;
  }, [dark]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let particles: Particle[] = [];
    let width = 0;
    let height = 0;
    let dpr = 1;
    let raf = 0;
    let visible = !document.hidden;

    function resize() {
      const parent = canvas!.parentElement;
      if (!parent) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = parent.clientWidth;
      height = parent.clientHeight;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Density scales with area, clamped to a sane range on very small/large screens.
      const count = Math.min(110, Math.max(35, Math.round((width * height) / 16000)));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        r: Math.random() * 1.6 + 1,
        accent: Math.random() < 0.15,
      }));
    }

    function draw() {
      const isDark = darkRef.current;
      ctx!.clearRect(0, 0, width, height);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x <= 0 || p.x >= width) p.vx *= -1;
        if (p.y <= 0 || p.y >= height) p.vy *= -1;
        p.x = Math.min(Math.max(p.x, 0), width);
        p.y = Math.min(Math.max(p.y, 0), height);
      }

      // Bonds - a line between any two particles closer than LINK_DIST,
      // fading out with distance.
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i];
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < LINK_DIST) {
            const alpha = (1 - dist / LINK_DIST) * (isDark ? 0.5 : 0.32);
            ctx!.strokeStyle = `rgba(${PRIMARY_RGB}, ${alpha})`;
            ctx!.lineWidth = 1;
            ctx!.beginPath();
            ctx!.moveTo(a.x, a.y);
            ctx!.lineTo(b.x, b.y);
            ctx!.stroke();
          }
        }
      }

      // Atoms - most are primary purple, a few accent gold, on top of the bonds.
      for (const p of particles) {
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx!.fillStyle = p.accent
          ? `rgba(${ACCENT_RGB}, ${isDark ? 0.85 : 0.7})`
          : `rgba(${PRIMARY_RGB}, ${isDark ? 0.85 : 0.6})`;
        ctx!.fill();
      }
    }

    function loop() {
      if (visible) draw();
      raf = requestAnimationFrame(loop);
    }

    resize();
    draw();
    if (!prefersReducedMotion) {
      raf = requestAnimationFrame(loop);
    }

    const onResize = () => resize();
    const onVisibility = () => {
      visible = !document.hidden;
    };
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
}
