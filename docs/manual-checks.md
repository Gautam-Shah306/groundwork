# Groundwork Manual UI & Responsive Verification Guide

This document specifies the responsive and visual checklist for Groundwork across mobile (375 px), tablet (768 px), and desktop (1280 px+) screen widths, per `docs/design-system.md` Section 16 and responsive design rules.

---

## 1. Global Shell & Navigation

### 375 px (Mobile)
- [ ] **Sidebar & Drawer**: Persistent desktop sidebar is hidden. Top navigation bar displays the mobile menu button (hamburger icon).
- [ ] **Drawer Interaction**: Clicking hamburger opens the mobile sidebar drawer with a backdrop overlay; clicking the overlay or selecting a link dismisses the drawer.
- [ ] **Breadcrumbs & Active Item**: TopBar shows compact breadcrumb trail and operational system status pill without horizontal page overflow.
- [ ] **Touch Targets**: All navigation links, buttons, and interactive icons have touch targets $\ge 36\text{ px}\times 36\text{ px}$.

### 768 px (Tablet)
- [ ] **Header Alignment**: Header elements (title, engagement selector, health pill) fit comfortably on a single line or wrap cleanly.
- [ ] **Drawer Navigation**: Drawer opens smoothly without layout shift.

### 1280 px (Desktop)
- [ ] **Persistent Sidebar**: Desktop 240 px sidebar is fixed and sticky (`sticky top-0 h-screen`).
- [ ] **Content Centering**: Main content wrapper respects `max-w-[var(--content-max-width)]` (1440 px) with comfortable padding (`px-10 py-8`).

---

## 2. Screen-by-Screen Checks

### Stage 00: Overview (`/`)
- **375 px**:
  - [ ] Stage progress indicator chips wrap cleanly without clipping.
  - [ ] Problem statement card text wraps naturally with proper contrast.
  - [ ] Quick navigation cards stack vertically in a single column (`grid-cols-1`).
  - [ ] Recent audit activity list displays human-readable sentences with date pills aligned.
- **768 px**:
  - [ ] Quick navigation cards display in a 2-column grid (`sm:grid-cols-2`).
- **1280 px**:
  - [ ] 3-column layout (`lg:grid-cols-3`) for summary cards and 4-column layout for stage cards.

### Engagements (`/engagements`)
- **375 px**:
  - [ ] "New engagement" form inputs and buttons stack vertically.
  - [ ] Engagements data table scrolls horizontally inside its card container (`overflow-x-auto`); page body does NOT scroll horizontally.
  - [ ] Stage badge and synthetic data indicator pill remain visible in table cells.
- **768 px & 1280 px**:
  - [ ] Form displays inputs in two columns where appropriate. Table shows all columns without clipping.

### Stage 01: Discover (`/discovery`)
- **375 px**:
  - [ ] Notes sidebar (`lg:col-span-4`) stacks below or above the main brief editor (`lg:col-span-8`).
  - [ ] Interview note cards display title, date, character count, and action buttons cleanly.
  - [ ] Note selection checkboxes are operable with touch.
  - [ ] "Analyse Notes with AI" button is prominent and easily clickable.
  - [ ] Follow-up questions panel and Version History snapshot list stack vertically.
- **768 px**:
  - [ ] Single-column layout or flex column maintains full editor width.
- **1280 px**:
  - [ ] 2-column layout (8 columns for brief editor, 4 columns for interview notes and version history).

### Stage 02: Diagnose (`/diagnostics`)
- **375 px**:
  - [ ] Ticket CSV upload dropzone renders cleanly. Action buttons ("Choose CSV file", "Load sample dataset") wrap gracefully.
  - [ ] Assistant panel stacks below data validation table and charts.
  - [ ] Validation check table scrolls horizontally within container.
  - [ ] Recharts bar/line charts resize dynamically or display container horizontal scroll; "View as table" toggle button remains accessible.
- **768 px**:
  - [ ] Validation check breakdown cards render cleanly in 2 columns.
- **1280 px**:
  - [ ] Analytical charts and assistant panel render side-by-side or stacked per section layout (`xl:flex-row`).

### Stage 03: Build — Prototypes (`/prototypes`)
- **375 px**:
  - [ ] Accessible tablist (`Triage workspace` and `Agent evaluation`) is full-width with touch-friendly tabs.
  - [ ] **Triage tab**: Ticket intake form stacks above proposal inbox list and review panel.
  - [ ] **Agent evaluation tab**: Run controls (sample size, drafts sample, Run Evaluation button) stack cleanly.
  - [ ] Confusion matrix and slice performance tables scroll horizontally inside their card wrappers; page has no horizontal overflow.
- **768 px**:
  - [ ] Evaluation KPI tiles render in a $3\times 2$ grid (`grid-cols-2 md:grid-cols-3`).
- **1280 px**:
  - [ ] Triage workspace renders split-view layout (`lg:col-span-5` inbox, `lg:col-span-7` proposal detail).
  - [ ] Evaluation KPI tiles render in a single 6-column row (`lg:grid-cols-6`).

### Stage 04: Measure — Outcomes (`/outcomes`)
- **375 px**:
  - [ ] KPI framework tiles stack vertically in a single column.
  - [ ] Baseline computation status and stale markers are clearly visible.
  - [ ] Interventions table scrolls within container; custom intervention form fields stack vertically.
  - [ ] Simulation sliders (ticket volume, auto-triage share, rework share) are touch-friendly.
  - [ ] Human confirmation review checkboxes and approval action buttons are easily operable.
- **768 px**:
  - [ ] KPI cards render in 2-column grid (`sm:grid-cols-2`).
- **1280 px**:
  - [ ] KPI framework displays in 3-column grid (`lg:grid-cols-3`).
  - [ ] Simulation configuration and result charts render side-by-side.

---

## 3. General Design System Invariants
- [ ] No horizontal scroll on `document.body` at any breakpoint.
- [ ] No raw JSON or stack traces displayed anywhere in the UI.
- [ ] All typography uses Inter for UI text and Instrument Serif selectively for primary headers.
- [ ] All simulated figures explicitly labelled with `<TypeLabel type="simulated_result" />`.
- [ ] All AI recommendations explicitly labelled with `<TypeLabel type="ai_recommendation" />`.
