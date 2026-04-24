"use client";

import { useEffect, useRef } from "react";

export default function CursorTrail() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const tctx = canvas.getContext("2d");
    if (!tctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const TRAIL_MAX = 36;
    const FADE_MS = 550;
    const trailPts: { x: number; y: number; t: number }[] = [];
    const trailSparkles: {
      x: number; y: number; life: number; size: number;
      vx: number; vy: number; kind: number;
    }[] = [];
    let trailCurX = -1, trailCurY = -1, trailSparkleTimer = 0;

    const onMouseMove = (e: MouseEvent) => {
      trailPts.push({ x: e.clientX, y: e.clientY, t: Date.now() });
      if (trailPts.length > TRAIL_MAX) trailPts.shift();
      trailCurX = e.clientX;
      trailCurY = e.clientY;
    };
    document.addEventListener("mousemove", onMouseMove);

    const spawnSparkle = (x: number, y: number) => {
      const type = Math.random();
      trailSparkles.push({
        x, y, life: 1,
        size: Math.random() * 4 + 2.5,
        vx: (Math.random() - 0.5) * 1.6,
        vy: (Math.random() - 0.5) * 1.6 - 0.8,
        kind: type < 0.45 ? 0 : type < 0.8 ? 1 : 2,
      });
    };

    let rafId: number;
    const draw = () => {
      tctx.clearRect(0, 0, canvas.width, canvas.height);
      const now = Date.now();

      // ── Ribbon trail ───────────────────────────────────────────
      if (trailPts.length >= 2) {
        for (let i = 1; i < trailPts.length; i++) {
          const p0 = trailPts[i - 1];
          const p1 = trailPts[i];
          const progress = i / trailPts.length;
          const age = (now - p1.t) / FADE_MS;
          const alpha = Math.max(0, progress * (1 - age) * 0.72);
          if (alpha < 0.01) continue;

          const w = progress * 3.8 + 0.4;
          const r0 = Math.round(30 + (1 - progress) * 20);
          const g0 = Math.round(77 + (1 - progress) * 40);
          const b0 = Math.round(146 + (1 - progress) * 60);

          tctx.beginPath();
          tctx.moveTo(p0.x, p0.y);
          tctx.lineTo(p1.x, p1.y);
          tctx.strokeStyle = `rgba(${r0},${g0},${b0},${alpha})`;
          tctx.lineWidth = w;
          tctx.lineCap = "round";
          tctx.lineJoin = "round";
          tctx.stroke();
        }
      }

      // ── Head glow ──────────────────────────────────────────────
      if (trailCurX > 0 && trailPts.length > 0) {
        const glow = tctx.createRadialGradient(trailCurX, trailCurY, 0, trailCurX, trailCurY, 14);
        glow.addColorStop(0, "rgba(42,102,190,0.22)");
        glow.addColorStop(1, "rgba(42,102,190,0)");
        tctx.beginPath();
        tctx.arc(trailCurX, trailCurY, 14, 0, Math.PI * 2);
        tctx.fillStyle = glow;
        tctx.fill();
      }

      // ── Spawn sparkles ─────────────────────────────────────────
      if (trailCurX > 0 && now - trailSparkleTimer > 70) {
        spawnSparkle(trailCurX, trailCurY);
        trailSparkleTimer = now;
      }

      // ── Draw & age sparkles ────────────────────────────────────
      for (let i = trailSparkles.length - 1; i >= 0; i--) {
        const sp = trailSparkles[i];
        sp.life -= 0.038;
        sp.x += sp.vx;
        sp.y += sp.vy;
        sp.vy += 0.04;
        if (sp.life <= 0) { trailSparkles.splice(i, 1); continue; }

        const a = sp.life * 0.85;
        const s = sp.size * Math.min(1, sp.life * 2.5);
        tctx.save();
        tctx.globalAlpha = a;
        tctx.strokeStyle = "#1e4d92";
        tctx.lineWidth = 1.4;
        tctx.translate(sp.x, sp.y);

        if (sp.kind === 0) {
          tctx.beginPath();
          tctx.moveTo(-s, 0); tctx.lineTo(s, 0);
          tctx.moveTo(0, -s); tctx.lineTo(0, s);
          tctx.stroke();
        } else if (sp.kind === 1) {
          tctx.rotate(Math.PI / 4);
          tctx.beginPath();
          tctx.moveTo(-s, 0); tctx.lineTo(s, 0);
          tctx.moveTo(0, -s); tctx.lineTo(0, s);
          tctx.stroke();
        } else {
          tctx.beginPath();
          tctx.moveTo(0, -s); tctx.lineTo(s * 0.6, 0);
          tctx.lineTo(0, s); tctx.lineTo(-s * 0.6, 0);
          tctx.closePath();
          tctx.fillStyle = `rgba(30,77,146,${a * 0.35})`;
          tctx.fill();
          tctx.stroke();
        }
        tctx.restore();
      }

      // Clean expired trail points
      const cutoff = now - FADE_MS;
      while (trailPts.length && trailPts[0].t < cutoff) trailPts.shift();

      rafId = requestAnimationFrame(draw);
    };

    rafId = requestAnimationFrame(draw);

    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: -1,
      }}
    />
  );
}
