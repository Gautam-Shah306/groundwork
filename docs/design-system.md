# Groundwork --- UI/UX Design System

**Version:** 1.0\
**Product:** Groundwork --- Business Operations Intelligence\
**Design direction:** Swiss Operational Minimalism\
**Aesthetic:** Editorial Enterprise\
**Theme:** Light only\
**Primary use:** Desktop-first business operations workspace

------------------------------------------------------------------------

## 1. Design philosophy

Groundwork should feel like a serious internal business product used by
consultants, business analysts, product managers and operations teams.

Its interface should communicate precision, clarity, restraint and
trust. It should support focused work across discovery, diagnosis,
prototyping and outcome measurement without looking like a generic AI
dashboard.

### Core principles

1.  **Clarity over decoration** --- every visual element should help
    users understand information or take action.
2.  **Evidence before recommendation** --- distinguish observed facts,
    assumptions, hypotheses and AI-generated suggestions.
3.  **Consistent structure** --- use predictable layouts, grids, spacing
    and component behaviour.
4.  **Calm information density** --- show enough operational detail to
    support decisions without overwhelming the user.
5.  **AI as a collaborator** --- integrate AI into the workflow instead
    of making a chatbot the entire product.
6.  **Outcome-oriented design** --- keep business objectives, KPIs,
    decisions and next actions visible.
7.  **Trust through transparency** --- show data sources, calculation
    definitions, limitations, tool activity and approval states.

### Visual character

-   Swiss-inspired grid and alignment.
-   Editorial typography with restrained serif display moments.
-   Neutral, warm surfaces.
-   Muted slate-blue accent.
-   Fine borders and minimal shadows.
-   Compact, legible controls.
-   Clear tables and analytical visualisations.
-   No decorative gradients, glassmorphism or excessive rounded cards.

------------------------------------------------------------------------

## 2. Brand and identity

### Wordmark

**Groundwork**

Use Instrument Serif for the wordmark where appropriate. Keep the
wordmark simple and typographic.

### Descriptor

**BUSINESS OPERATIONS INTELLIGENCE**

Use Inter, uppercase, with restrained letter spacing.

### Brand voice

-   Clear and direct.
-   Analytical, not robotic.
-   Confident without overstating certainty.
-   Practical and action-oriented.
-   Avoid exaggerated AI language and marketing claims.

### Suggested product language

Prefer: - "Finding to validate" - "Evidence" - "Working hypothesis" -
"Recommended next step" - "Awaiting approval" - "Baseline" - "Outcome
review"

Avoid: - "AI magic" - "Revolutionary intelligence" - "Guaranteed
improvement" - "Autonomous decision" when human approval is required.

------------------------------------------------------------------------

## 3. Colour system

Use a warm-neutral foundation with deep ink typography and a restrained
slate-blue accent.

### Core colours

  Token              Hex         Usage
  ------------------ ----------- ------------------------------------------
  `canvas`           `#F7F7F4`   Main application background
  `surface`          `#FFFFFF`   Cards, panels, tables and forms
  `ink`              `#202A35`   Primary text and strong actions
  `muted`            `#687482`   Secondary text and supporting labels
  `accent`           `#526B89`   Primary accent, links and active states
  `accent-soft`      `#EEF2F6`   Accent backgrounds and selected surfaces
  `border`           `#E7E9E8`   Dividers, outlines and card borders
  `surface-subtle`   `#FAFAF8`   Secondary inset surfaces

### Semantic colours

  -----------------------------------------------------------------------
  Token             Hex               Background        Usage
  ----------------- ----------------- ----------------- -----------------
  `success`         `#267A59`         `#EAF4EF`         Completed,
                                                        healthy, approved

  `warning`         `#A96F2C`         `#F8F0E5`         Needs attention,
                                                        validation
                                                        required

  `danger`          `#B84D49`         `#F8ECEB`         Critical issue,
                                                        failed action

  `info`            `#526B89`         `#EEF2F6`         Informational
                                                        state
  -----------------------------------------------------------------------

### Colour rules

-   Use accent blue sparingly. It should identify interaction and focus,
    not decorate every card.
-   Use semantic colours only when they communicate a meaningful state.
-   Do not rely on colour alone to communicate status; pair it with a
    label or icon.
-   Use red only for genuinely critical or destructive situations.
-   Maintain sufficient contrast for text and interactive controls.
-   Keep the application light-only for the initial product.

------------------------------------------------------------------------

## 4. Typography

Use two typefaces with distinct roles.

### Primary interface typeface --- Inter

Use Inter for: - Navigation. - Body text. - Buttons and controls. -
Forms and input labels. - Tables and data labels. - Charts and KPI
labels. - Metadata and timestamps. - AI responses and operational
content.

### Display typeface --- Instrument Serif

Use Instrument Serif selectively for: - Main page headings. - Important
introductory statements. - Brand wordmark. - Occasional editorial
emphasis. - Large KPI values where the context benefits from a softer
editorial character.

Do not use Instrument Serif for dense operational information, tables,
forms or small labels.

### Type scale

  -------------------------------------------------------------------------
  Style                           Size               Weight Typical use
  --------------- -------------------- -------------------- ---------------
  Display / page             40--44 px                  400 Main page
  title                                                     heading,
                                                            Instrument
                                                            Serif

  Section heading            20--24 px             500--600 Major content
                                                            sections

  Card heading               12--14 px             600--700 Card and panel
                                                            titles

  Body                           13 px             400--500 Default
                                                            application
                                                            text

  Supporting body            11--12 px                  400 Secondary
                                                            descriptions

  Label                       9--10 px             600--700 Metadata, field
                                                            labels

  Eyebrow                         9 px                  700 Uppercase
                                                            section markers

  KPI value                  28--32 px                  400 Large metric
                                                            values,
                                                            Instrument
                                                            Serif
  -------------------------------------------------------------------------

### Typography rules

-   Use sentence case for most interface labels.
-   Use uppercase only for compact metadata and eyebrow labels.
-   Keep line lengths comfortable for reading.
-   Use tabular numerals for metrics, dates, durations and financial
    figures.
-   Use consistent line heights; avoid compressed body text.
-   Never use decorative italic text as a substitute for hierarchy.

------------------------------------------------------------------------

## 5. Layout system

### Application shell

Use a persistent left sidebar and a flexible main workspace.

**Desktop layout:** - Sidebar: approximately 220--240 px. - Main
content: flexible remaining width. - Top bar: approximately 64--66 px
high. - Main content maximum width: approximately 1,380 px. - Main
content horizontal padding: approximately 40 px on large screens.

### Sidebar

-   Light, subtly differentiated background.
-   Fine right border.
-   Wordmark and descriptor at the top.
-   Grouped navigation links.
-   Clear active navigation state.
-   Settings and user profile anchored near the bottom.
-   Compact iconography with consistent stroke weight.

### Top bar

-   Breadcrumbs on the left.
-   Lightweight system status, help and user access on the right.
-   Fine bottom border.
-   Avoid unnecessary search bars or action clutter.

### Main workspace

-   Use a consistent grid.
-   Prefer two-column layouts for overview pages.
-   Use a wider primary content column and a narrower contextual column.
-   Allow full-width analytical tables and visualisations when needed.
-   Keep related information grouped.
-   Use whitespace to separate sections rather than excessive card
    nesting.

### Grid and spacing

Use a 4 px base spacing unit.

  Token          Value Usage
  ------------ ------- ---------------------------
  `space-1`       4 px Tight icon/text spacing
  `space-2`       8 px Compact control spacing
  `space-3`      12 px Small component gaps
  `space-4`      16 px Default component spacing
  `space-5`      20 px Card interior spacing
  `space-6`      24 px Section spacing
  `space-8`      32 px Major layout gaps
  `space-10`     40 px Page padding
  `space-12`     48 px Large section separation

Use consistent spacing tokens rather than arbitrary values.

------------------------------------------------------------------------

## 6. Surfaces, borders and elevation

### Surface hierarchy

1.  **Canvas:** warm off-white application background.
2.  **Primary surface:** white cards, panels and work areas.
3.  **Inset surface:** subtle warm-neutral backgrounds for quoted
    content, summaries and grouped information.
4.  **Selected surface:** pale blue background for active or selected
    elements.

### Borders

-   Default border: `1px solid #E7E9E8`.
-   Use subtle dividers inside cards and tables.
-   Avoid heavy outlines.
-   Use stronger borders only for focused, selected or validation
    states.

### Shadows

Use minimal shadows, primarily to separate floating elements from the
canvas.

Suggested shadow:

``` css
box-shadow: 0 7px 24px rgba(32, 42, 53, 0.03);
```

Do not use prominent shadows on every card.

### Corner radius

  Component             Radius
  ------------------ ---------
  Small controls       4--5 px
  Cards and panels     6--8 px
  Inputs               5--6 px
  Status pills          999 px
  Avatars                  50%

Avoid excessively rounded, playful surfaces.

------------------------------------------------------------------------

## 7. Component system

### Buttons

**Primary** - Deep ink background. - White text. - Used for the most
important action on a screen.

**Secondary** - White background. - Fine neutral border. - Dark text.

**Tertiary** - Text-only or subtle background. - Used for low-emphasis
actions.

**Destructive** - Semantic danger treatment. - Used only for destructive
actions.

Button rules: - Compact height, generally 34--40 px. - Clear action
labels. - Consistent icon alignment. - Visible hover, focus, active and
disabled states. - Avoid multiple competing primary buttons in one area.

### Cards

-   White surface.
-   Fine neutral border.
-   6--8 px radius.
-   Minimal shadow.
-   Consistent internal padding, generally 16--20 px.
-   Clear heading and supporting description.
-   Do not place every individual data point in its own card.

### Inputs and forms

-   White background.
-   Neutral border.
-   Clear field label above the control.
-   Supporting text below where useful.
-   Visible focus state using the accent colour.
-   Validation message close to the relevant field.
-   Distinguish required fields from optional fields.
-   Do not rely on placeholder text as the only label.

### Navigation

-   Compact labels.
-   Consistent icons.
-   Subtle active background.
-   Active text in deep ink.
-   Avoid decorative navigation badges.
-   Use counts only when they convey useful information.

### Status indicators

Use small semantic pills with a text label.

Examples: - In progress - Needs validation - Awaiting approval -
Completed - Blocked - Critical

Do not use colour without a corresponding status label.

### Tables

Tables are a core component of Groundwork.

-   White surface.
-   Compact but comfortable row height.
-   Uppercase, letter-spaced column headings.
-   Subtle horizontal dividers.
-   Left-align descriptive text.
-   Right-align numerical values where appropriate.
-   Use tabular numerals.
-   Support sorting and filtering when useful.
-   Provide empty, loading and error states.
-   Avoid excessive vertical grid lines.

### KPI components

Each KPI should show: - Metric name. - Value. - Unit. - Measurement
period. - Baseline or comparison where available. - Direction or status
where meaningful.

Do not show a target or improvement percentage without a defined source
and calculation.

### Charts

-   Restrained colour palette.
-   Clear axes and labels.
-   Meaningful units and time ranges.
-   Tooltips for exact values.
-   Avoid 3D charts and decorative effects.
-   Use consistent colours for the same metric across screens.
-   Clearly distinguish actual, baseline, target and forecast values.

------------------------------------------------------------------------

## 8. AI interaction design

AI should feel like a capable colleague working alongside the user---not
a chatbot pasted into the application.

### Interaction model

Use a contextual assistant panel or workspace that can access the
current engagement and relevant data.

The assistant should be able to: - Understand the user's objective. -
Ask clarifying questions. - Select relevant tools. - Analyse available
evidence. - Present findings. - Explain recommendations. - Propose
actions. - Request human approval.

### Three visual states

**1. Analysis** - Show what the agent is investigating. - Indicate tools
being used. - Display progress without pretending the agent has
completed work. - Make tool activity inspectable.

**2. Findings** - Present structured observations. - Show supporting
evidence. - Distinguish facts from hypotheses. - Explain missing data
and limitations.

**3. Actions** - Present the proposed action and its consequences. -
Provide approve, edit and reject controls. - Show the action's current
status. - Record the decision in an audit trail.

### AI trust principles

-   Never present generated assumptions as verified facts.
-   Cite or link findings to their supporting data when possible.
-   Explain uncertainty and limitations.
-   Keep calculations deterministic.
-   Require human approval for consequential actions.
-   Show when an action has actually succeeded or failed.
-   Preserve an audit trail of proposed and approved actions.

### Assistant visual treatment

-   Use the muted accent colour for AI identity.
-   Keep the assistant visually integrated with the active workspace.
-   Avoid large gradient backgrounds, glowing effects and oversized bot
    avatars.
-   Use structured response blocks for findings, recommendations and
    actions.

------------------------------------------------------------------------

## 9. Screen-level design patterns

### Overview

Purpose: Give the user a concise view of engagement progress and
important work.

Recommended structure: - Greeting and date. - New engagement action. -
Active engagement summary. - Current problem statement. - Engagement
stage and progress. - Contextual AI insight. - Next best actions. -
Important operational metrics. - Diagnostic findings. - Recent activity.

### Discovery

Purpose: Understand the client's business and define the problem.

Recommended structure: - Client and engagement context. - Interview
notes or transcript. - AI-generated themes. - Confirmed facts. -
Assumptions and unknowns. - Follow-up questions. - Editable problem
statement.

Use an editorial, document-oriented layout.

### Diagnostics

Purpose: Investigate operational evidence.

Recommended structure: - Dataset overview. - Upload and validation
state. - Data-quality warnings. - KPI summary. - Charts and analytical
tables. - Findings with supporting evidence. - Hypotheses requiring
validation.

Prioritise analytical clarity and traceability.

### Prototypes

Purpose: Demonstrate and test a working intervention.

Recommended structure: - Prototype overview. - Operational work queue. -
AI recommendation. - Evidence and reasoning. - Proposed action. - Human
approval controls. - Action history.

Make the prototype usable, not merely presentational.

### Outcomes

Purpose: Evaluate whether an intervention made a difference.

Recommended structure: - Outcome objective. - KPI definitions. -
Baseline and target. - Pilot or comparison period. - Actual results. -
Comparison charts. - Limitations and caveats. - Continue, modify, expand
or stop recommendation.

Clearly label simulated results.

------------------------------------------------------------------------

## 10. Iconography

-   Use a consistent outline icon family.
-   Prefer simple, recognisable symbols.
-   Use consistent 16 px icons in navigation and controls.
-   Use 18--20 px icons for prominent actions.
-   Use icons alongside labels where meaning may be ambiguous.
-   Avoid mixing filled, outlined and illustrative icon styles.

Icons should support scanning, not become decoration.

------------------------------------------------------------------------

## 11. Interaction and feedback

Every interactive component should have clearly designed states.

### Required states

-   Default.
-   Hover.
-   Focus.
-   Active or selected.
-   Disabled.
-   Loading.
-   Success.
-   Warning.
-   Error.
-   Empty.

### Feedback principles

-   Confirm successful uploads and saved changes.
-   Show progress for longer-running analysis.
-   Explain failures in actionable language.
-   Preserve user input when validation fails.
-   Confirm consequential actions before execution.
-   Provide undo or reversal where practical.
-   Do not use success styling before an operation has actually
    succeeded.

------------------------------------------------------------------------

## 12. Responsive behaviour

Groundwork is desktop-first because its workflows involve analysis,
tables and multiple contextual panels.

### Desktop

-   Persistent sidebar.
-   Multi-column workspace.
-   Contextual assistant panel.
-   Full analytical tables and charts.

### Tablet

-   Narrower sidebar or collapsible navigation.
-   Reduce multi-column layouts.
-   Keep primary content visible.
-   Move contextual panels below or alongside the main content when
    space allows.

### Mobile

-   Replace persistent sidebar with compact navigation.
-   Stack content vertically.
-   Convert wide tables into readable responsive layouts.
-   Keep primary actions accessible.
-   Avoid shrinking desktop layouts without restructuring them.

------------------------------------------------------------------------

## 13. Accessibility and usability

-   Maintain readable text contrast.
-   Ensure keyboard navigation.
-   Provide visible focus indicators.
-   Use semantic headings and labels.
-   Give form controls accessible names.
-   Do not communicate status through colour alone.
-   Make interactive targets comfortably usable.
-   Support browser zoom and responsive text.
-   Provide clear error messages.
-   Avoid unnecessary motion; respect reduced-motion preferences.

------------------------------------------------------------------------

## 14. Content and data integrity

Because Groundwork supports business decisions, interface copy must be
precise.

Always distinguish:

  Type                Meaning
  ------------------- ---------------------------------------------
  Observed fact       Directly supported by supplied data
  Client statement    Reported by a stakeholder
  Hypothesis          A possible explanation requiring validation
  AI recommendation   A proposed course of action
  Approved action     Explicitly accepted by an authorised person
  Measured outcome    Calculated from defined observations
  Simulated result    Generated for demonstration or testing

Use explicit labels for these distinctions throughout the application.

Never imply that synthetic demonstration data represents a real client
engagement.

------------------------------------------------------------------------

## 15. Design tokens --- CSS reference

``` css
:root {
  /* Colours */
  --color-canvas: #F7F7F4;
  --color-surface: #FFFFFF;
  --color-surface-subtle: #FAFAF8;
  --color-ink: #202A35;
  --color-muted: #687482;
  --color-accent: #526B89;
  --color-accent-soft: #EEF2F6;
  --color-border: #E7E9E8;

  --color-success: #267A59;
  --color-success-soft: #EAF4EF;
  --color-warning: #A96F2C;
  --color-warning-soft: #F8F0E5;
  --color-danger: #B84D49;
  --color-danger-soft: #F8ECEB;

  /* Typography */
  --font-interface: "Inter", sans-serif;
  --font-display: "Instrument Serif", Georgia, serif;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;

  /* Radius */
  --radius-control: 5px;
  --radius-card: 7px;
  --radius-pill: 999px;

  /* Borders and elevation */
  --border-default: 1px solid var(--color-border);
  --shadow-subtle: 0 7px 24px rgba(32, 42, 53, 0.03);

  /* Layout */
  --sidebar-width: 230px;
  --topbar-height: 64px;
  --content-max-width: 1380px;
}
```

------------------------------------------------------------------------

## 16. Design quality checklist

Before accepting any new screen or component, verify:

-   [ ] It follows the warm-neutral and slate-blue colour system.
-   [ ] Inter is used for operational interface content.
-   [ ] Instrument Serif is used selectively.
-   [ ] Alignment follows a consistent grid.
-   [ ] Spacing uses the defined tokens.
-   [ ] Borders are subtle and consistent.
-   [ ] Shadows are minimal.
-   [ ] Information hierarchy is immediately clear.
-   [ ] Tables and numerical data are easy to scan.
-   [ ] Facts, hypotheses and recommendations are visually
    distinguishable.
-   [ ] AI activity and proposed actions are transparent.
-   [ ] Consequential actions require appropriate approval.
-   [ ] Loading, empty, error and success states are designed.
-   [ ] The screen works at desktop, tablet and mobile widths.
-   [ ] No decorative element competes with the work.

------------------------------------------------------------------------

## 17. Final design direction

**Groundwork --- Swiss Operational Minimalism with an Editorial
Enterprise aesthetic.**

The product should look composed, precise and dependable. Its visual
identity should come from disciplined typography, a strong grid, clear
data presentation and thoughtful AI interaction---not from visual
effects.

The guiding principle:

> A workspace where business problems are understood, evidence is
> examined, solutions are tested and outcomes are measured.
