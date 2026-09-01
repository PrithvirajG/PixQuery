// Aperture blocks — composed pieces built from kit.js primitives.
//
// kit.js holds single-purpose primitives (buttons, toggles, chips). Blocks are
// one level up: small compositions with their own domain vocabulary — a pipeline
// run's lifecycle, a model output's shape — reused across views that show
// per-image pipeline state (currently ImageDetails; PipelineStatsView shows the
// same lifecycle at the workspace level).
import React, { useState } from 'react';
import { AP, STATUS } from './tokens';
import { IconBtn, EyeBtn } from './kit';

/* ── inline icons for pipeline controls ───────────────────────── */
// Small stroke icons for the reprocess/delete cluster and the collapse
// chevron — kept local rather than exported from kit.js because they're
// single-purpose glyphs for these specific controls, not general primitives.
// The eye icon lives in kit.js as part of `EyeBtn` — it's a real button in
// its own right, not a glyph private to this file.
function ReprocessIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M20 12a8 8 0 1 1-2.6-5.9" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />
      <path d="M20 3.6V7.4h-3.8" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function TrashIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4.5 7h15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M9.5 4.5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M6.6 7.5l.8 11a1.6 1.6 0 0 0 1.6 1.5h6a1.6 1.6 0 0 0 1.6-1.5l.8-11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10.4 11v6M13.6 11v6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
function ChevronIcon({ collapsed }) {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      style={{ transform: collapsed ? 'rotate(-90deg)' : 'none', transition: 'transform .14s' }}
    >
      <path d="M6 9.5l6 6 6-6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
// Bare, unbordered — distinct from the bordered IconBtn cluster, matching how
// the section's own collapse control reads as chrome rather than an action.
function ChevronBtn({ collapsed, onClick, title }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        width: 20,
        height: 20,
        borderRadius: 6,
        background: 'transparent',
        border: 0,
        padding: 0,
        color: collapsed ? AP.ink3 : AP.lumen,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        flex: '0 0 auto',
      }}
    >
      <ChevronIcon collapsed={collapsed} />
    </button>
  );
}

/* ── confidence meter ─────────────────────────────────────────── */

// A short filled bar plus its numeric value, out of 1 — the confidence readout
// beside every detected object or label.
export function Meter({ v }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, flex: '0 0 auto' }}>
      <span style={{ width: 40, height: 4, borderRadius: 99, background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
        <span
          style={{
            display: 'block',
            height: '100%',
            width: `${Math.round(v * 100)}%`,
            background: AP.lumenGrad,
            borderRadius: 99,
          }}
        />
      </span>
      <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink2, width: 30, textAlign: 'right' }}>
        {v.toFixed(2)}
      </span>
    </span>
  );
}

/* ── per-object colour ────────────────────────────────────────── */

// 8 hues, one lightness/chroma, stepped ~33° apart so no two are close enough
// to confuse. Chosen against the working set (a single result almost always
// shows 3-8 classes), not the class vocabulary — collisions past 8 distinct
// labels in one task are an accepted tradeoff, cheaper than hues nobody can
// tell apart, and the label text + box position still disambiguate. Hue
// 0-99 is reserved and left unused: STATUS.err sits at ~15, Ember at ~55, and
// this keeps every object colour clear of both by a comfortable margin.
const OBJ_HUES = [283, 250, 217, 183, 150, 117, 317, 350];

// Deterministic per-object colour, shared by ObjRow's swatch/highlight and the
// bbox overlay so a detection row and its box on the image always agree
// without hovering anything — same colour function, both sides.
//
// Hashes `${task}:${name}`, not the row's index (rows sort by confidence and
// would reshuffle every run) and not `name` alone (two different detectors —
// object detection vs face detection — can each emit a label like "person";
// namespacing by task keeps them from fighting over one colour). `task` is
// the producing model (`model_name`) so it's stable per detector.
//
// `alpha` returns the same hue as a translucent fill/tint (e.g. a row's hover
// highlight, or a box's fill) instead of the opaque swatch/stroke colour.
export function objColor(task, name, alpha) {
  const key = `${task ?? 'default'}:${name}`;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0;
  }
  const hue = OBJ_HUES[Math.abs(hash) % OBJ_HUES.length];
  return alpha == null ? `oklch(0.74 0.14 ${hue})` : `oklch(0.74 0.14 ${hue} / ${alpha})`;
}

/* ── detected/labeled object row ──────────────────────────────── */

// One detected object or classification label: name, an optional repeat count,
// a confidence Meter, and — when `onToggle` is supplied — a checkbox that hides
// its boxes on an overlay elsewhere on the page. Hover state is lifted to the
// caller (`onHoverEnter`/`onHoverLeave`) so it can drive that same overlay.
// `task` (usually the producing model's name) keys the row's colour via
// `objColor` — pass the same value used for the overlay's boxes so a row and
// its box agree. Toggled off (`onToggle` present and `checked` false) dims
// the whole row and strikes the label, since the hidden boxes are otherwise
// invisible in the list.
export function ObjRow({ name, n, c, task, checked = true, onToggle, onHoverEnter, onHoverLeave, highlighted = false }) {
  const color = objColor(task, name);
  const off = !!onToggle && !checked;
  return (
    <div
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
        borderRadius: 6,
        padding: '3px 5px',
        margin: '-3px -5px',
        background: highlighted ? objColor(task, name, 0.17) : 'transparent',
        opacity: off ? 0.45 : 1,
        transition: 'background .12s, opacity .12s',
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        {onToggle ? (
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            style={{ width: 13, height: 13, accentColor: color, cursor: 'pointer', flex: '0 0 auto' }}
          />
        ) : (
          <span style={{ width: 9, height: 9, borderRadius: 2, background: color, flex: '0 0 auto' }} />
        )}
        <span
          style={{
            fontFamily: AP.sans,
            fontSize: 13.5,
            color: AP.ink,
            whiteSpace: 'nowrap',
            textDecorationLine: off ? 'line-through' : 'none',
            textDecorationColor: AP.ink4,
          }}
        >
          {name}
          {n > 1 ? <span style={{ color: AP.ink3 }}> ×{n}</span> : ''}
        </span>
      </span>
      <Meter v={c} />
    </div>
  );
}

/* ── muted helper text ────────────────────────────────────────── */

// Small dim paragraph for empty/explanatory states ("No objects detected.",
// "Not processed yet — use Process to run this pipeline.").
export const Muted = ({ children }) => (
  <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 12, color: AP.ink3, lineHeight: 1.5 }}>{children}</p>
);

/* ── one pipeline output, by type ─────────────────────────────── */

const OUTPUT_LABEL = {
  caption: 'Caption',
  detections: 'Detections',
  labels: 'Classification',
  ocr: 'OCR text',
  written_image: 'Written image',
};

function aggregateDetections(dets) {
  return Object.values(
    (dets || []).reduce((acc, d) => {
      const k = d.label ?? 'object';
      if (!acc[k]) acc[k] = { name: k, n: 0, c: 0 };
      acc[k].n += 1;
      acc[k].c = Math.max(acc[k].c, d.confidence ?? 0);
      return acc;
    }, {})
  ).sort((a, b) => b.c - a.c);
}

// Renders one output's payload by its `output_type` (caption / detections /
// labels / ocr / written_image / anything else). `detectionState` — only
// meaningful for "detections" — wires each row's checkbox + hover to a bbox
// overlay elsewhere on the page; omit it to render the rows read-only.
export function OutputBody({ o, detectionState }) {
  const p = o.payload || {};
  if (o.output_type === 'caption') {
    return (
      <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 13.5, lineHeight: 1.5, color: AP.ink, fontStyle: 'italic' }}>
        “{p.text || o.summary}”
      </p>
    );
  }
  if (o.output_type === 'detections') {
    const rows = aggregateDetections(p.detections);
    return rows.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        {rows.map((r) => (
          <ObjRow
            key={r.name}
            name={r.name}
            n={r.n}
            c={r.c}
            task={o.model_name}
            checked={!detectionState?.hiddenLabels?.has(r.name)}
            onToggle={() => detectionState?.toggleLabel(r.name)}
            onHoverEnter={() => detectionState?.setHoveredLabel(r.name)}
            onHoverLeave={() => detectionState?.setHoveredLabel(null)}
            highlighted={detectionState?.hoveredLabel === r.name}
          />
        ))}
      </div>
    ) : <Muted>No objects detected.</Muted>;
  }
  if (o.output_type === 'labels') {
    const labels = p.labels || [];
    return labels.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        {labels.map((l, i) => <ObjRow key={i} name={l.label} n={1} c={l.confidence ?? 0} task={o.model_name} />)}
      </div>
    ) : <Muted>No labels.</Muted>;
  }
  if (o.output_type === 'ocr') {
    return <p style={{ margin: 0, fontFamily: AP.mono, fontSize: 12, color: AP.ink2, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{p.text || '—'}</p>;
  }
  if (o.output_type === 'written_image') {
    const wi = p.written_image || {};
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink, wordBreak: 'break-all' }}>{wi.path || '—'}</span>
        {wi.width ? <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>{wi.width}×{wi.height} · {wi.format}</span> : null}
      </div>
    );
  }
  return <Muted>{o.summary || 'Output recorded.'}</Muted>;
}

// The human label for one output's type — "Detections", "Caption", etc.
// Exported so callers building their own stage chrome (StageCard) around
// OutputBody don't need their own copy of OUTPUT_LABEL.
export function outputLabel(o) {
  return OUTPUT_LABEL[o.output_type] || o.output_type;
}

/* ── per-output-type glyph ────────────────────────────────────────
   One small icon per `output_type`, so a run's stages read apart from each
   other at a glance instead of every StageCard header looking identical.
   Keyed on `output_type` (what a stored model output actually carries),
   not `node_type` — a purely-transform node (resize, grayscale, embedding)
   never produces its own model_output row, so it never reaches this list;
   there's nothing here to give it an icon for. Unrecognized types (a future
   output_type, or a legacy one) render with no icon rather than a guess. */
function DetectionsIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
function ClassificationIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M11.5 4H6.5A2.5 2.5 0 0 0 4 6.5v5c0 .66.26 1.3.73 1.77l8 8a2.5 2.5 0 0 0 3.54 0l5-5a2.5 2.5 0 0 0 0-3.54l-8-8A2.5 2.5 0 0 0 11.5 4z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <circle cx="8.7" cy="8.7" r="1.15" fill="currentColor" stroke="none" />
    </svg>
  );
}
function CaptionIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v6a2.5 2.5 0 0 1-2.5 2.5H10l-4 4v-4H7.5A2.5 2.5 0 0 1 5 12.5v-6z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function OcrIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M6 3.5h8l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-16a1 1 0 0 1 1-1z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M14 3.5V8h4.5" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M8 12.5h8M8 15.5h8M8 18.5h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
function WrittenImageIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="8.7" cy="9.7" r="1.4" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4.5 16.5l4.3-4.3a1.8 1.8 0 0 1 2.55 0l3.2 3.2 1.3-1.3a1.8 1.8 0 0 1 2.55 0l2.6 2.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
const OUTPUT_ICON = {
  detections: DetectionsIcon,
  labels: ClassificationIcon,
  caption: CaptionIcon,
  ocr: OcrIcon,
  written_image: WrittenImageIcon,
};

// The glyph for one output's type, or `null` for a type with no icon defined
// — StageCard renders fine either way. Same keying/fallback shape as
// `outputLabel`, kept alongside it since both read the same vocabulary.
export function outputIcon(o) {
  const Icon = OUTPUT_ICON[o.output_type];
  return Icon ? <Icon /> : null;
}

/* ── one numbered stage within an expanded pipeline section ──────
   A stage's own page-visibility eye — mirrors the section-level eye at
   finer grain, hiding just this one stage's body without touching its
   siblings. Delete/retry stay pipeline-wide only: model outputs have no
   per-node id yet, so there's nothing to scope either action to. `icon` is
   optional and caller-supplied (see `outputIcon`) — StageCard itself stays
   agnostic to what kind of stage it's chrome for. */
export function StageCard({ index, total, name, icon, trailing, hidden = false, onToggleHidden, children }) {
  return (
    <div style={{ border: `1px solid ${AP.line2}`, borderRadius: 11, background: AP.card, overflow: 'hidden' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          padding: '9px 12px',
          borderBottom: hidden ? 'none' : `1px solid ${AP.line}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <EyeBtn on={!hidden} onClick={onToggleHidden} size={20} />
          {icon && (
            <span style={{ display: 'inline-flex', color: hidden ? AP.ink3 : AP.lumenSoft, flex: '0 0 auto' }}>
              {icon}
            </span>
          )}
          {total > 1 && (
            <span
              style={{
                fontFamily: AP.mono,
                fontSize: 9.5,
                color: AP.ink3,
                border: `1px solid ${AP.line2}`,
                borderRadius: 5,
                padding: '2px 5px',
                whiteSpace: 'nowrap',
                flex: '0 0 auto',
              }}
            >
              {index}/{total}
            </span>
          )}
          <span
            style={{
              fontFamily: AP.sans,
              fontSize: 12.5,
              fontWeight: 500,
              color: hidden ? AP.ink2 : AP.ink,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {name}
          </span>
        </div>
        {trailing && (
          <span style={{ fontFamily: AP.mono, fontSize: 10, color: AP.ink3, whiteSpace: 'nowrap', flex: '0 0 auto' }}>
            {trailing}
          </span>
        )}
      </div>
      {!hidden && <div style={{ padding: '10px 12px' }}>{children}</div>}
    </div>
  );
}

/* ── pipeline run lifecycle ───────────────────────────────────── */

// One (image, pipeline) pair's lifecycle, mirrored from the API's `state`.
const STATE_META = {
  not_started: { label: 'Not started', c: AP.ink3, bg: 'rgba(255,255,255,0.05)', line: AP.line2 },
  queued: { label: 'Queued', c: AP.lumenSoft, bg: AP.lumenBg, line: AP.lumenLine },
  processing: { label: 'Processing', c: AP.lumenSoft, bg: AP.lumenBg, line: AP.lumenLine },
  completed: { label: 'Completed', c: STATUS.ok.c, bg: STATUS.ok.bg, line: STATUS.ok.line },
  failed: { label: 'Failed', c: STATUS.err.c, bg: STATUS.err.bg, line: STATUS.err.line },
};

// In-flight states can't be dispatched again (the backend rejects it with a 409).
// Exported so callers can share this exact definition of "in flight" rather than
// re-deriving it (e.g. to decide whether stored outputs are still trustworthy).
export const IN_FLIGHT = new Set(['queued', 'processing']);

// Small pill naming a pipeline run's current lifecycle state (Not started /
// Queued / Processing / Completed / Failed), colored per STATE_META.
export function StatePill({ state }) {
  const meta = STATE_META[state] || STATE_META.not_started;
  return (
    <span
      style={{
        fontFamily: AP.mono,
        fontSize: 9.5,
        lineHeight: 1,
        color: meta.c,
        background: meta.bg,
        border: `1px solid ${meta.line}`,
        borderRadius: 6,
        padding: '3px 6px',
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
      }}
    >
      {meta.label}
    </span>
  );
}

// "stage 3/5 · captioning" — live progress inside a single run. Renders nothing
// until the first stage of a run reports in (`stage` is null/undefined then).
export function StageProgress({ stage }) {
  if (!stage) return null;
  return (
    <span style={{ fontFamily: AP.mono, fontSize: 10, color: AP.lumenSoft, whiteSpace: 'nowrap' }}>
      stage {stage.index}/{stage.total}
      {stage.node_type ? ` · ${stage.node_type}` : ''}
    </span>
  );
}

// The full pipeline card: a chevron collapses the card itself down to one
// summary row; an eye/reprocess/delete control cluster in the top-right
// corner (eye always shown, reprocess/delete only when their handler is
// given); an inline error line when failed; and — while expanded and shown
// (`!collapsed && on`) — its outputs as `children`. `section` is `{ name,
// id?, state, stage?, detached?, lastError?, hasOutputs, model }`; `model` is
// a short trailing label (e.g. "3 outputs").
//
// The chevron and the eye are deliberately independent: the chevron collapses
// the section itself (pure layout, held as local state — nothing outside this
// card depends on it), while the eye governs what the section displays
// on the page (`on`/`toggle` are lifted to the caller because they also drive
// a bbox overlay elsewhere on the page). Collapsing hides everything below
// the header regardless of the eye; expanded-but-hidden shows the header and
// meta row but no outputs.
export function PipelineSection({
  section,
  on,
  toggle,
  onProcess,
  processing,
  onDelete,
  deleting,
  children,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const running = !!processing || IN_FLIGHT.has(section.state);

  const meta = (
    <>
      <StatePill state={section.state} />
      {section.detached && (
        <span
          style={{
            fontFamily: AP.mono,
            fontSize: 9.5,
            lineHeight: 1,
            color: AP.ember,
            background: AP.emberBg,
            border: `1px solid ${AP.emberLine}`,
            borderRadius: 6,
            padding: '3px 6px',
            whiteSpace: 'nowrap',
          }}
          title="This pipeline is no longer attached to the workspace — past outputs only"
        >
          Detached
        </span>
      )}
      <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>{section.model}</span>
    </>
  );

  return (
    <div
      style={{
        borderRadius: 13,
        border: `1px solid ${on ? AP.lumenLine : AP.line}`,
        background: on ? AP.lumenBg : 'rgba(255,255,255,0.015)',
        padding: '13px 14px',
        transition: 'all .16s',
        opacity: on ? 1 : 0.72,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <ChevronBtn
              collapsed={collapsed}
              onClick={() => setCollapsed((c) => !c)}
              title={collapsed ? 'Expand this pipeline' : 'Collapse this pipeline'}
            />
            <span style={{ fontFamily: AP.sans, fontSize: 14, fontWeight: 600, color: on ? AP.ink : AP.ink2 }}>
              {section.name}
            </span>
            {section.id && (
              <span
                style={{
                  fontFamily: AP.mono,
                  fontSize: 10,
                  color: on ? AP.lumenSoft : AP.ink3,
                  padding: '1px 6px',
                  borderRadius: 6,
                  background: 'rgba(255,255,255,0.04)',
                  border: `1px solid ${on ? AP.lumenLine : AP.line2}`,
                  flex: '0 0 auto',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: 110,
                }}
              >
                #{section.id}
              </span>
            )}
            {collapsed && meta}
          </div>
          {!collapsed && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', paddingLeft: 20, marginTop: 5 }}>
              {meta}
              <StageProgress stage={section.stage} />
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flex: '0 0 auto' }}>
          <EyeBtn on={on} onClick={toggle} size={27} />
          {onProcess && (
            <IconBtn
              size={27}
              active={running}
              spin={running}
              disabled={running}
              onClick={onProcess}
              title={
                running
                  ? 'Already running — wait for it to finish'
                  : section.state === 'completed'
                    ? 'Re-run this pipeline — replaces its existing outputs'
                    : 'Run this pipeline against this image'
              }
            >
              <ReprocessIcon />
            </IconBtn>
          )}
          {onDelete && (
            <IconBtn
              size={27}
              tone="danger"
              spin={!!deleting}
              disabled={!section.hasOutputs || !!deleting}
              onClick={onDelete}
              title={
                section.hasOutputs
                  ? 'Delete this pipeline’s outputs for this image (it can be run again afterwards)'
                  : 'Nothing to delete — this pipeline has no stored outputs for this image'
              }
            >
              <TrashIcon />
            </IconBtn>
          )}
        </div>
      </div>
      {!collapsed && section.state === 'failed' && section.lastError && (
        <div style={{ paddingLeft: 20, marginTop: 8 }}>
          <span
            style={{
              fontFamily: AP.sans,
              fontSize: 11,
              color: STATUS.err.c,
              display: 'block',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={section.lastError}
          >
            {section.lastError}
          </span>
        </div>
      )}
      {!collapsed && on && <div style={{ paddingTop: 13, paddingLeft: 20 }}>{children}</div>}
    </div>
  );
}
