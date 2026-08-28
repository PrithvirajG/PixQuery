// Aperture blocks — composed pieces built from kit.js primitives.
//
// kit.js holds single-purpose primitives (buttons, toggles, chips). Blocks are
// one level up: small compositions with their own domain vocabulary — a pipeline
// run's lifecycle, a model output's shape — reused across views that show
// per-image pipeline state (currently ImageDetails; PipelineStatsView shows the
// same lifecycle at the workspace level).
import React, { useState } from 'react';
import { AP, STATUS } from './tokens';
import { Toggle } from './kit';

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
            textDecoration: off ? 'line-through' : 'none',
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

// One model output as a labeled card: its type/model name in the header, its
// payload rendered by OutputBody below.
export function OutputCard({ o, detectionState }) {
  return (
    <div style={{ borderRadius: 9, border: `1px solid ${AP.line2}`, background: 'rgba(255,255,255,0.02)', padding: '10px 11px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontFamily: AP.sans, fontSize: 12.5, fontWeight: 600, color: AP.ink }}>
          {OUTPUT_LABEL[o.output_type] || o.output_type}
        </span>
        <span style={{ fontFamily: AP.mono, fontSize: 9.5, color: AP.ink3 }}>
          {o.model_name}{o.model_version ? ` · ${o.model_version}` : ''}
        </span>
      </div>
      <OutputBody o={o} detectionState={detectionState} />
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

// "Process" for a pair that has never produced output, "Reprocess" once it has.
// Disabled while `busy` (an in-flight request from this client) or while `state`
// is itself queued/processing (already running, dispatched from elsewhere).
export function ProcessButton({ state, onClick, busy }) {
  const inFlight = IN_FLIGHT.has(state);
  const disabled = busy || inFlight;
  const label = state === 'completed' ? '↻ Reprocess' : '▶ Process';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={
        inFlight
          ? 'Already running — wait for it to finish'
          : state === 'completed'
            ? 'Re-run this pipeline — replaces its existing outputs'
            : 'Run this pipeline against this image'
      }
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 8px',
        borderRadius: 7,
        flex: '0 0 auto',
        fontFamily: AP.sans,
        fontSize: 11,
        fontWeight: 500,
        lineHeight: 1.2,
        color: disabled ? AP.ink4 : AP.ink2,
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${AP.line2}`,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
        whiteSpace: 'nowrap',
      }}
    >
      {busy ? '⋯ Working' : label}
    </button>
  );
}

// Deletes a pipeline's stored outputs (for one image). Sits beside a visibility
// toggle in real use because the two are easy to confuse: a toggle hides
// outputs locally, this deletes them on the server. `disabled` when there is
// nothing stored to delete.
export function DeleteOutputsBtn({ onClick, busy, disabled }) {
  const [hover, setHover] = useState(false);
  const off = disabled || busy;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={off}
      aria-label="Delete outputs"
      title={
        disabled
          ? 'Nothing to delete — this pipeline has no stored outputs for this image'
          : 'Delete this pipeline’s outputs for this image (it can be run again afterwards)'
      }
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 26,
        height: 22,
        borderRadius: 7,
        flex: '0 0 auto',
        fontSize: 12,
        lineHeight: 1,
        cursor: off ? 'not-allowed' : 'pointer',
        color: off ? AP.ink4 : hover ? STATUS.err.c : AP.ink3,
        background: hover && !off ? STATUS.err.bg : 'rgba(255,255,255,0.03)',
        border: `1px solid ${hover && !off ? STATUS.err.line : AP.line2}`,
        opacity: off ? 0.5 : 1,
        transition: 'all .12s',
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {busy ? '⋯' : '🗑'}
    </button>
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

// The full pipeline card: name/id header, state pill, optional "Detached"
// badge, delete + visibility controls, a Process/Reprocess button, an inline
// error line when failed, and — while expanded (`on`) — its outputs as
// `children`. `section` is `{ name, id?, state, stage?, detached?, lastError?,
// hasOutputs, model }`; `model` is a short trailing label (e.g. "3 outputs").
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: on ? AP.lumen : AP.ink4, flex: '0 0 auto' }}>◇</span>
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
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              flexWrap: 'wrap',
              paddingLeft: 20,
              marginTop: 5,
            }}
          >
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
            <StageProgress stage={section.stage} />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: '0 0 auto' }}>
          {onDelete && (
            <DeleteOutputsBtn
              onClick={onDelete}
              busy={!!deleting}
              disabled={!section.hasOutputs}
            />
          )}
          <Toggle on={on} onClick={toggle} />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 20, marginTop: 10 }}>
        {onProcess && (
          <ProcessButton state={section.state} onClick={onProcess} busy={!!processing} />
        )}
        {section.state === 'failed' && section.lastError && (
          <span
            style={{
              fontFamily: AP.sans,
              fontSize: 11,
              color: STATUS.err.c,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={section.lastError}
          >
            {section.lastError}
          </span>
        )}
      </div>
      {on && <div style={{ paddingTop: 13, paddingLeft: 20 }}>{children}</div>}
    </div>
  );
}
