## Aperture conventions

Aperture is PixQuery's design system: a dark "Carbon" canvas with a violet/indigo
"Lumen" intelligence accent and a rare orange "Ember" human accent. It ships as
plain functional React components with **no context provider, no theme wrapper,
no setup step** — import a component from this package and render it directly.
There is nothing to configure before it will look right.

### Styling idiom: a JS token object via inline styles — no CSS classes

Every component styles itself with an inline `style={{...}}` object built from
plain JS constants — **not** CSS custom properties, not Tailwind, not a
CSS-in-JS library. The tokens are exported from this bundle as `AP` and
`STATUS`; use them the same way the components themselves do, for any custom
layout markup you write that isn't already a component (a wrapping `<div>`,
a page section, spacing between components):

```jsx
import { AP, STATUS, Eyebrow, GhostBtn } from 'pixquery-aperture';

<div style={{ background: AP.panel, border: `1px solid ${AP.line}`, borderRadius: 13, padding: 16 }}>
  <Eyebrow>Section label</Eyebrow>
  <span style={{ fontFamily: AP.sans, fontSize: 14, color: AP.ink }}>Body text</span>
  <GhostBtn onClick={() => {}}>Action</GhostBtn>
</div>
```

Key `AP` tokens (there is no other source of truth for color/type — these
*are* the palette):

| Token | Value | Use |
|---|---|---|
| `AP.base` / `AP.panel` / `AP.card` / `AP.cardHi` | near-black surfaces, each one step lighter | page bg → rail/bar → card → hover |
| `AP.line` / `AP.line2` | `rgba(255,255,255,.07)` / `.13` | hairline borders, `.07` default, `.13` for emphasis |
| `AP.ink` / `AP.ink2` / `AP.ink3` / `AP.ink4` | near-white → dim, 4 steps | primary text → placeholder/disabled |
| `AP.lumen` / `AP.lumenSoft` / `AP.lumenBg` / `AP.lumenLine` / `AP.lumenGrad` | violet `#8b7bf7` family | the intelligence accent — active states, running jobs, AI-driven content |
| `AP.ember` / `AP.emberBg` / `AP.emberLine` | orange `#ef9355` family | rare — human/manual actions only, never a default |
| `AP.sans` / `AP.mono` | `'Geist', 'Inter', … sans-serif` / `'Geist Mono', … monospace` | body text / labels, numbers, code, ids |

`STATUS` is a parallel palette keyed by state name — `STATUS.ok/warn/err/run/queue/idle`,
each `{ c, bg, line }` (dot color, background tint, border) — used for health
pills, job status, and anywhere something is succeeding/failing/waiting rather
than just "on-brand".

A handful of effects that inline styles can't express ship as real CSS classes
(bound via `styles.css`, already in this bundle's `@import` closure — nothing
extra to link): `ap-photo`/`ap-vig` (the photo grain+vignette treatment, see
`Photo`), `ap-pulse`/`ap-pulse-dot`/`ap-shimmer` (loading/live-activity sheens,
see `Bar`'s `pulse` prop and `Shimmer`/`ShimmerCard`), `ap-scroll` (styled
scrollbars). Use these classes only via the components that already apply
them — don't hand-roll new ones; if you need a new animated affordance, ask
for a new component rather than reaching for arbitrary CSS.

### Where the truth lives

There is no separate tokens stylesheet — `AP`/`STATUS` are the tokens, and
they're plain named exports from this bundle (`import { AP, STATUS } from
'pixquery-aperture'`), not `var(--*)` custom properties. `styles.css` carries
only the small set of effect classes above. Each component's own `.d.ts` and
`.prompt.md` (bound alongside it) are the per-component API reference — read
those before composing a component you haven't used yet, especially
`PipelineSection` (the compound pipeline-run card) whose `section` prop is a
small object, not flat props.

### One idiomatic composition

```jsx
import { PipelineSection, OutputCard, AP } from 'pixquery-aperture';

<div style={{ width: 380, background: AP.base, padding: 16 }}>
  <PipelineSection
    section={{ name: 'Object Detection', state: 'completed', model: '2 outputs', hasOutputs: true }}
    on
    toggle={() => {}}
    onProcess={() => {}}
    onDelete={() => {}}
  >
    <OutputCard o={{ output_type: 'caption', model_name: 'blip', payload: { text: 'A busy street scene.' } }} />
  </PipelineSection>
</div>
```
