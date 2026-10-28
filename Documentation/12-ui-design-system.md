# UI Design System

## Design concept

The product's thesis is "proof over paperwork" — every claim (a skill, a certificate, a
score) gets checked against real evidence rather than taken at face value. The UI's job is
to make that verification visible: scores come with an evidence trail, not just a number;
fraud flags show the actual evidence, not an accusation; a candidate's Talent Score radar
chart links back to the raw signals that produced it.

The design intent (from the original design brief this doc is adapted from) leans toward a
confident, premium visual language rather than a plain "monospace receipt" look: rich
information density revealed through interaction, sophisticated use of color/shadow/depth to
express verification states (verified / unverified / flagged), bold typography in key
moments, restrained typography in body text, and generous, deliberate motion on state
changes (a score reveal, a verification result landing) rather than decoration for its own
sake.

That's a design *intent*, and it should be read as intent, not as a claim that every
ambitious visual idea in the original brief (3D/WebGL hero moments, custom canvas
animations, D3-driven data storytelling) shipped exactly as envisioned. The section below
lists what's actually installed and in use.

## Frontend libraries (actual, verified against `apps/web/package.json`)

| Purpose | Library | Version |
|---|---|---|
| Framework | Next.js (App Router) + TypeScript | 16.2.12 |
| UI runtime | React | 19.2.4 |
| Styling | Tailwind CSS | 4.x |
| Component primitives | shadcn | 4.16.0 |
| Headless UI primitives | @base-ui/react | 1.6.0 |
| Motion | framer-motion | 12.43.0 |
| Charts | recharts | 3.10.1 |
| Drag-and-drop (kanban) | @dnd-kit/core, @dnd-kit/sortable | 6.3.1 / 10.0.0 |
| Code editor | @monaco-editor/react | 4.7.0 |
| In-browser code execution | pyodide (in-browser Python, for coding assessments) | 314.0.3 |
| PDF export | html2pdf.js | 0.10.3 |
| Icons | lucide-react | 1.27.0 |
| Theming | next-themes | 0.4.6 |
| Toasts | sonner | 2.0.7 |
| Class utilities | class-variance-authority, clsx, tailwind-merge | — |
| E2E testing | @playwright/test | 1.62.0 |

Three.js, Spline, and D3 appear in the original design brief's aspirational tooling list but
are **not** dependencies in `apps/web/package.json` — they are not used in the shipped
frontend. Any 3D/canvas hero moments in the product, if present, are built with CSS/Framer
Motion rather than a dedicated WebGL library. This list reflects what's actually installed,
not the original design brief's full wishlist.

## Design language

**Color.** An extended palette beyond a minimal 6-color system: distinct color/luminance
treatment for verification states (verified, unverified, flagged) so trust status reads at a
glance rather than requiring a label; light and dark mode both get deliberate treatment via
`next-themes`, not just a naive color inversion.

**Typography.** A small number of font families used with intent — a stronger display face
for hero/key moments, a more restrained body face, monospace reserved for genuinely
technical content (code snippets, credential IDs, file paths).

**Layout.** No fixed 12-column dogma — generous whitespace where content should breathe
(landing sections, empty states), tighter clustering where information density is the point
(dashboards, evidence tables).

**Motion.** Framer Motion drives state-change animation: a score reveal, a verification
result landing, a kanban card moving stage. The intent is motion that communicates a change
happened and what it means, not motion as decoration layered on top of a static page.

## Copy voice

Plain, active, specific. Buttons describe exactly what they do. Errors are clear and
actionable. Empty states guide the user toward the next action rather than apologizing for
being empty.

## Where this lives

| Component | Path |
|---|---|
| Frontend app root | `apps/web/src/app/` |
| Shared components | `apps/web/src/components/` |
| Tailwind config | `apps/web/` (Tailwind 4 uses CSS-based config, not a `tailwind.config.js`) |
| Theme hook usage | `next-themes`'s `useTheme()`, e.g. `apps/web/src/components/ui/sonner.tsx` |
| Package manifest | `apps/web/package.json` |
