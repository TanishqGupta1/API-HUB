# Task 0.5 — Workflows Page (Pipeline Visualizer)

**Completed by:** Vidhi
**Branch:** `Vidhi`
**Date:** 2026-04-17
**Status:** ✅ Done — tested and committed

---

## In Simple Words (For Everyone)

This page shows the journey a product takes — from a supplier's warehouse all the way to your online store. It's a visual diagram so anyone (technical or not) can see exactly how the system works and whether each step is running, done, or idle.

Think of it like a flight tracker — instead of tracking a plane, you're tracking your product data moving through the pipeline.

---

## What the Page Shows

**Title:** Data Pipeline
**Subtitle:** How products flow from suppliers to your storefronts

### The 5-Node Pipeline Diagram

```
[🚛 Supplier] → [⬇️ Fetch Data] → [▽ Normalize] → [🗄️ Store in DB] → [🚀 Publish to Store]
```

| Node | Icon | What it does |
|------|------|-------------|
| Supplier | Truck | The wholesale supplier (SanMar, S&S, Alphabroder, 4Over) — where raw product data comes from |
| Fetch Data | Download arrow | Our system calls the supplier's API (SOAP or REST) and pulls the product catalog |
| Normalize | Funnel | Raw supplier data (different formats per supplier) is filtered and shaped into one clean standard format |
| Store in DB | Database | The cleaned data is saved into our PostgreSQL database |
| Publish to Store | Send arrow | Products are pushed into the OnPrintShop storefront with markup-applied pricing |

### Node Status Indicators

Each node shows its current state:

| Status | Color | Meaning |
|--------|-------|---------|
| idle | Gray | Not running — waiting |
| running | Blue (spinning) | Currently processing |
| done | Green | Completed successfully |
| error | Red (pulsing) | Something went wrong |

### Animated Connectors

The arrows between nodes animate when the left node is running — a blue dot travels along the line showing data flowing to the next step.

### Below the diagram

- **"Open n8n Editor ↗"** button — links to `http://localhost:5678` (the n8n workflow editor where sync schedules are configured)
- **Info panel:** "Sync schedules are managed in n8n. The pipeline runs automatically once activated."

---

## Files Changed

| File | What changed |
|------|-------------|
| `frontend/src/app/workflows/page.tsx` | Rewritten — clean static page with 5-node pipeline, correct title, info panel |
| `frontend/src/components/workflows/pipeline-view.tsx` | Updated — added SVG icon support per node, icon colors match node status |

---

## Is This Page Live?

**Not yet — it is static for V0.** All nodes show "idle" and the status never changes.

It becomes live in **Task 19 (V1e)** when:
- n8n workflows are deployed and running
- Backend gets a `/api/workflows/status` endpoint
- The page polls that endpoint every 5 seconds
- Node statuses update in real time based on actual sync jobs

---

## Why SVG Icons Instead of Emojis

The project uses the **Blueprint design system** — a clean, minimal, professional theme with:
- Paper background (`#f2f0ed`)
- Blueprint blue (`#1e4d92`)
- Fira Code monospace font
- Subtle borders and muted colors

Emojis clash with this theme — they are colorful and inconsistent across operating systems. The SVG icons used here are:
- Single-color (match the node's status color)
- Crisp at any size
- Consistent across all browsers and operating systems
- On-theme with the Blueprint design system

---

## How to Test

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/workflows` and verify:

1. Title shows **"Data Pipeline"**
2. Subtitle shows **"How products flow from suppliers to your storefronts"**
3. 5 nodes visible: Supplier → Fetch Data → Normalize → Store in DB → Publish to Store
4. All nodes show **idle** status (gray dot, gray border)
5. Each node has its SVG icon (truck, download arrow, funnel, database, send arrow)
6. Arrows connect all 5 nodes
7. **"Open n8n Editor ↗"** button visible below the diagram
8. Info panel text visible at the bottom

---

## Where This Fits in the Pipeline

```
Workflows Page (Task 0.5)  ◀── YOU ARE HERE
(static visualization — shows the pipeline concept)
        │
        ▼
V1a — Tasks 1-5
(backend pipeline actually built: SOAP client, normalizer, sync endpoints)
        │
        ▼
V1e — Task 19
(page becomes live — real-time status from n8n + sync jobs API)
```
