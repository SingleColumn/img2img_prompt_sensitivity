# Design Guide — img2img lab

This document records every significant design decision made for this project: the rationale, the rule that resulted, and (where relevant) what was tried first and why it was wrong. Its purpose is to allow future sessions to start from the final state without re-litigating the iterations that produced it.

---

## Aesthetic intent

Warm parchment — not sterile white, not dark. The palette evokes analogue materials: paper, ink, terracotta. The UI should feel like a research workbook, not a SaaS dashboard. Interactions are minimal and deliberate; there are no animations beyond the progress bar fill.

---

## Token reference

Tokens live in `frontend/src/styles/tokens.css`. All CSS values must use these tokens — no hardcoded hex, rgba, or pixel values except where a token does not exist.

### Surface hierarchy

Four levels, each progressively lighter/warmer. Elements at each level must sit on the level below them.

| Level | Token | Hex approx | Used for |
|---|---|---|---|
| Page | `--color-bg-page-1` / `--color-bg-page-2` | `#f6f1e8` → `#e7ddd0` | Full-page gradient background |
| Panel | `--color-surface` | `#fdf8f0` | `.panel` containers |
| Card | `--color-surface-muted` (60% mix) | warm cream tint | `.prompt-card` |
| Input | `--color-surface-raised` (solid) | `#fffdf9` | All `input`, `textarea`, `select` |

**Rule:** Each level must be visually distinct from the one it sits on. Never use `color-mix(…, transparent)` for interactive element backgrounds (inputs, selects, textareas) — the container is already a tinted surface, so a transparent mix produces near-zero contrast. Always use the solid token value for inputs.

This was discovered the hard way: `.field input` originally used `color-mix(in srgb, var(--color-surface-raised) 75%, transparent)`, which was nearly invisible against the card background. The fix was `background: var(--color-surface-raised)` (solid).

The same trap applies to any standalone selector (e.g. `.set-selector select`) that duplicates the `.field input` rule with its own explicit values — it must also be updated when the global rule changes.

### Border tokens

| Token | Use |
|---|---|
| `--color-border` | Structural dividers, panel outlines |
| `--color-border-strong` | Interactive element borders (inputs, selects, textareas) |
| `--color-border-accent` | Selected state (e.g. `.variation-select-card.selected`) |

**Rule:** Interactive element borders use `--color-border-strong`, not `--color-border`. The weaker token does not provide enough affordance that an element is interactive.

### Spacing tokens

```
--space-1: 4px    gap within a tight cluster (image-meta rows)
--space-2: 8px    field-gap (label to input), small gaps
--space-3: 12px   gap between fields inside a card
--space-4: 16px   standard gap: between cards, section content margin-top
--space-5: 24px   panel-gap, panel-padding, results-stack gap
--space-6: 32px   page padding, hero padding
```

**Rule:** Use tokens for every spacing value. When a raw pixel value appears, replace it with the nearest token — do not create intermediate values.

**Rule:** Content that follows a `.section-heading` uses `margin-top: var(--space-4)` if it is a standalone element (e.g. `.set-selector`, `.form-grid`). Content inside a flex/grid column card uses `gap` on the container, not individual `margin-top` on children.

---

## Component patterns

### Panel

```jsx
<section className="panel">
  <div className="section-heading">
    <div>
      <p className="section-kicker">Label</p>
      <h2>Title</h2>
    </div>
    <button className="primary-button">Action</button>
  </div>
  {/* content */}
</section>
```

`.section-heading` is `display: flex; justify-content: space-between`. The left child is always a `<div>` containing the kicker + heading. The right child is an action button or `null`.

### Prompt card grid

Cards use CSS grid with `repeat(auto-fit, minmax(290px, 1fr))`. All cards in a row must reach the same height and have their textarea start at the same vertical position.

Structure that achieves this:
```
.prompt-card         display:flex; flex-direction:column; gap:var(--space-3)
  .prompt-card-header
  .field              (variation name)
  .field              (variation type)
  .field.field-block.field-grow   (prompt textarea)
```

- `.prompt-card` flex column with `gap: var(--space-3)` owns all vertical spacing between children.
- `.field-block { margin-top: 0 }` is overridden inside `.prompt-card` — the gap handles it.
- `.field-grow` is `flex: 1; display: flex; flex-direction: column` — it absorbs all remaining height.
- `.field-grow textarea` is `flex: 1; min-height: 9rem; resize: none` — fills its wrapper, never collapses below ~6 lines.

**Rule:** The Baseline card must have the same field structure as variation cards (Variation name + Variation type fields, even if disabled) so all cards in the row share the same vertical rhythm and textareas start at the same position.

**Rule:** The prompt card header (`name + similarity pill`) must never use `flex-wrap`. If the title div is wide, it should shrink (`flex: 1; min-width: 0`) rather than push the pill to a new line. A wrapped pill falls to the left under `justify-content: space-between`, which looks broken.

### Prompt card header

```css
.prompt-card-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: var(--space-2);
  /* NO flex-wrap */
}

.prompt-card-header > div:first-child {
  flex: 1;        /* absorbs width, shrinks when narrow */
  min-width: 0;   /* allows shrinking below intrinsic size */
  overflow-wrap: break-word;
}

.similarity-pill {
  flex-shrink: 0; /* never shrinks — stays pinned top-right */
}
```

The header contains only: `<div>` (title) and `.similarity-pill`. The kicker label (variation type) was removed — it duplicated the Variation type field below it. One source of truth.

### Form grid (prompt builder)

```css
.form-grid {
  grid-template-columns: minmax(0, 1.2fr) auto 180px;
  align-items: center;   /* NOT end */
  margin-top: var(--space-4);
}
```

`align-items: center` vertically centres all grid items in the row. `align-items: end` was used initially and required a `margin-top: 26px` hack on the checkbox field to make it look aligned — a sign the alignment strategy was wrong. With `center`, no hacks needed.

The checkbox field (`<label class="field checkbox-field">`) has `grid-template-columns: auto 1fr` to lay out the checkbox and its label text horizontally. No `margin-top` override needed.

### Variation select cards (Prompts to run)

```jsx
<label className="variation-select-card [selected]">
  <input type="checkbox" />
  <span>                        {/* flex column container */}
    <span className="vsc-name">Label</span>
    <span className="vsc-excerpt">prompt text...</span>
  </span>
</label>
```

Critical rules:
1. `.variation-select-card > span` must be `display: flex; flex-direction: column` so name and excerpt stack vertically instead of flowing inline.
2. `.variation-select-card input[type="checkbox"]` must have `width: auto` — these cards are nested inside `<div class="field field-block">`, so the `.field input { width: 100% }` rule reaches the checkboxes and stretches them to fill the entire card if not overridden.

### Checkbox lists (Models field)

Same issue: `.checkbox-item input[type="checkbox"]` needs `width: auto; flex-shrink: 0` because the list is inside a `.field` div and the global rule would otherwise make checkboxes full-width.

**Rule:** Any `input[type="checkbox"]` that sits inside a `.field` container (directly or nested) must have `width: auto` explicitly set. The global `.field input { width: 100% }` rule does not discriminate by input type.

### Tab bar

```css
.tab-bar {
  background: var(--color-surface-raised);  /* solid — NOT transparent */
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  box-shadow: 0 2px 8px rgba(64, 39, 20, 0.06);
}
```

`background: var(--color-surface)` was insufficient — the tab bar was nearly invisible against the page background gradient. `var(--color-surface-raised)` (the lightest, most distinct surface) with a full border and shadow gives it clear visual separation.

### Sidebar layout (Past runs)

```css
.past-runs-layout {
  grid-template-columns: 240px minmax(0, 1fr);
}
```

The content column uses `minmax(0, 1fr)` not `1fr`. Without `minmax(0, …)`, the column's minimum size is the intrinsic content width, which can cause overflow. With `minmax(0, 1fr)`, the column is allowed to shrink below its content width, and `overflow: hidden` on children works correctly.

Long run IDs in the 240px sidebar need `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` and a `title` attribute on the button for full text on hover.

---

## Typography

- **Display / headings:** `--font-display` (Georgia serif) — gives the UI its editorial, analogue feel
- **UI / body:** `--font-ui` (system sans-serif stack)
- **Eyebrow / kicker labels:** uppercase, `--tracking-eyebrow` (0.14em), `--color-accent`, `--text-xs`

**Rule:** Font sizes must come from tokens (`--text-xs` through `--text-display`). Raw rem or px font sizes are not permitted. Where a size like `0.88rem` appeared in the original code, it was replaced with the nearest token (`--text-base: 0.92rem`).

---

## Known CSS pitfalls in this codebase

These were all discovered through iteration and fixed. Document them so they are not repeated.

### 1. `flex-wrap` on headers containing pills

**Problem:** A flex container with `flex-wrap: wrap` and `justify-content: space-between` causes a wrapped item to align to `flex-start` on its new line, not `flex-end`. A similarity pill that wraps appears at the left under the title — looks broken.  
**Fix:** Remove `flex-wrap`. Give the title div `flex: 1; min-width: 0` so it shrinks before the pill wraps.

### 2. `color-mix` with transparency for interactive backgrounds

**Problem:** `color-mix(in srgb, var(--color-surface-raised) 75%, transparent)` composites the surface colour against whatever is behind it. When the background is already a tinted surface (as in a card), the result is nearly invisible.  
**Fix:** Use the solid token value. Interactive element backgrounds must be opaque.

### 3. Duplicate standalone selectors not inheriting updated global rules

**Problem:** `.set-selector select` had its own explicit `border` and `background` declarations. When the global `.field select` rule was updated, the standalone selector still used the old values.  
**Fix:** Audit any element that has both a standalone CSS rule and falls under a global rule. The standalone rule always wins — it must be updated explicitly.

### 4. `width: 100%` reaching checkbox inputs

**Problem:** `.field input { width: 100% }` applies to all inputs inside `.field` regardless of type. Checkboxes inside `.variation-select-card` (which is inside `<div class="field field-block">`) were stretched to card width, rendering as large coloured rectangles that covered the text.  
**Fix:** Any selector targeting a specific checkbox must explicitly set `width: auto`.

### 5. `align-items: end` on form grids requiring compensating margins

**Problem:** Using `align-items: end` on a multi-column form grid required a `margin-top` hack on the checkbox field to make it appear visually aligned. The hack was fragile and varied with content height.  
**Fix:** Use `align-items: center` for mixed-height form rows. The visual alignment is natural without hacks.

### 6. `flex: 1` on textarea without `min-height`

**Problem:** A `flex: 1` textarea inside a flex column card collapses to near-zero height when the card is small (no content forcing height). The textarea was effectively invisible.  
**Fix:** `min-height: 9rem` (≈ 6 lines at `--text-base` × `--leading-body`) ensures a usable minimum. `flex: 1` still allows growth in tall rows.

### 7. `.venv` and `node_modules` path sensitivity

Not a UI issue, but affects the project's runtime. The backend `paths.py` uses `Path(__file__).resolve().parents[3]` as APP_ROOT. This depth is load-bearing — it is correct for both the current layout (`img2img_lab/backend/app/core/`) and the target post-restructure layout (`backend/app/core/`). Do not change it. The `.venv` hardcodes the absolute path to its creation location and must not be moved — delete and recreate after any directory restructure.
