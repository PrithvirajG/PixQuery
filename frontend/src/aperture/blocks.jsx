// Aperture blocks — composed pieces built from kit.js primitives.
//
// kit.js holds single-purpose primitives (buttons, toggles, chips). Blocks are
// one level up: small compositions with their own domain vocabulary — a pipeline
// run's lifecycle, a model output's shape — reused across views that show
// per-image pipeline state (currently ImageDetails; PipelineStatsView shows the
// same lifecycle at the workspace level).
import React, { useState } from 'react';
import { AP, STATUS } from './tokens';
import { IconBtn, EyeBtn, Eyebrow } from './kit';

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

/* ── readable text colour over an arbitrary swatch ────────────── */

// Black or white, whichever stays legible on `hex` — picked from the swatch's
// own relative luminance (WCAG's channel curve). A palette is arbitrary user
// data, so neither a fixed colour nor a `mix-blend-mode` survives every input:
// difference-blending white went muddy and unreadable on mid-tone oranges.
// Falls back to near-white for anything that isn't a 6-digit hex.
export function readableOn(hex) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(hex ?? ''));
  if (!match) return 'rgba(255,255,255,.92)';
  const int = parseInt(match[1], 16);
  const [r, g, b] = [(int >> 16) & 255, (int >> 8) & 255, int & 255].map((channel) => {
    const s = channel / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.42
    ? 'rgba(0,0,0,.78)'
    : 'rgba(255,255,255,.92)';
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
  image_stats: 'Image quality',
  aesthetic_score: 'Aesthetic score',
  nsfw_flag: 'Content flag',
  color_palette: 'Color palette',
  open_vocab_detections: 'Open-vocabulary detection',
  segments: 'Segments',
  annotations: 'Annotations',
  species: 'Species ID',
  scene: 'Scene',
  geo_estimate: 'Location estimate',
  depth: 'Depth',
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
// `writtenImage` — only meaningful for "written_image" — supplies the saved
// file's URL plus the compare toggle (`{ src, comparing, onToggleCompare }`),
// since the component can't know an API base of its own; omit it and the card
// falls back to the plain path/dimensions text.
export function OutputBody({ o, detectionState, writtenImage }) {
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
    const meta = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
        <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink, wordBreak: 'break-all' }}>{wi.path || '—'}</span>
        {wi.width ? <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>{wi.width}×{wi.height} · {wi.format}</span> : null}
      </div>
    );
    // No `src` supplied (a preview card, or a caller that can't serve the file)
    // → the original text-only rendering. The component never builds the URL
    // itself: it has no notion of an API base, and must render standalone.
    if (!writtenImage?.src) {
      return <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>{meta}</div>;
    }
    const comparing = !!writtenImage.comparing;
    const toggle = writtenImage.onToggleCompare;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            type="button"
            onClick={toggle}
            disabled={!toggle}
            title={toggle ? (comparing ? 'Stop comparing' : 'Compare with the original') : undefined}
            style={{
              width: 44, height: 44, borderRadius: 8, overflow: 'hidden', padding: 0,
              flex: '0 0 auto', background: AP.cardHi,
              border: `1px solid ${comparing ? AP.lumenLine : AP.line2}`,
              boxShadow: comparing ? `0 0 0 2px ${AP.lumenBg}` : 'none',
              cursor: toggle ? 'pointer' : 'default',
            }}
          >
            <img src={writtenImage.src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
          </button>
          {meta}
        </div>
        {toggle && (
          <span style={{ fontFamily: AP.sans, fontSize: 11, color: comparing ? AP.lumenSoft : AP.ink3 }}>
            {comparing ? 'Comparing with the original — drag the divider' : 'Click the thumbnail to compare with the original'}
          </span>
        )}
      </div>
    );
  }
  if (o.output_type === 'image_stats') {
    const fields = [
      ['Sharp', p.sharpness], ['Exposure', p.exposure], ['Contrast', p.contrast],
      ['Bright', p.brightness], ['Color', p.colorfulness],
    ].filter(([, v]) => v != null);
    return fields.length ? (
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${fields.length}, minmax(0,1fr))`, gap: 14 }}>
        {fields.map(([label, v]) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Eyebrow>{label}</Eyebrow>
            <span style={{ fontFamily: AP.sans, fontSize: 19, fontWeight: 600, color: AP.ink }}>{Math.round(v)}</span>
          </div>
        ))}
      </div>
    ) : <Muted>No quality metrics recorded.</Muted>;
  }
  if (o.output_type === 'aesthetic_score') {
    const score = p.score ?? 0;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ fontFamily: AP.sans, fontSize: 19, fontWeight: 600, color: AP.ink }}>
            {score.toFixed(1)} <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3, fontWeight: 400 }}>/ 10</span>
          </span>
          <span style={{ width: 130, height: 5, borderRadius: 99, background: 'rgba(255,255,255,0.09)', overflow: 'hidden', flex: '0 0 auto' }}>
            <span style={{ display: 'block', height: '100%', width: `${Math.round((score / 10) * 100)}%`, borderRadius: 99, background: AP.lumenGrad }} />
          </span>
        </div>
        <Muted>Taste-based, not an objective quality score — trained on human preference ratings, biased toward saturated/high-contrast images.</Muted>
      </div>
    );
  }
  if (o.output_type === 'nsfw_flag') {
    const flagged = !!p.flagged;
    const tone = flagged ? STATUS.err : STATUS.ok;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: tone.bg, border: `1px solid ${tone.line}`, borderRadius: 999, padding: '3px 10px 3px 8px' }}>
            <span style={{ width: 6, height: 6, borderRadius: 99, background: tone.c, boxShadow: flagged ? `0 0 8px ${tone.c}` : 'none' }} />
            <span style={{ fontFamily: AP.sans, fontSize: 12, fontWeight: 500, color: tone.c }}>{flagged ? 'Flagged for review' : (p.label || 'Clear')}</span>
          </span>
          {p.score != null && <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink2 }}>{p.score.toFixed(2)} confidence</span>}
        </div>
        <Muted>Binary flag only — treat as a review prompt, never an automatic action.</Muted>
      </div>
    );
  }
  if (o.output_type === 'color_palette') {
    const colors = p.colors || [];
    return colors.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {colors.map((c, i) => (
            <span key={i} style={{ flex: 1, height: 44, borderRadius: 9, background: c.hex, border: `1px solid ${AP.line2}`, position: 'relative' }}>
              <span style={{ position: 'absolute', left: 6, bottom: 5, fontFamily: AP.mono, fontSize: 9, color: readableOn(c.hex) }}>{c.hex}</span>
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {p.dominant && <span style={{ fontFamily: AP.sans, fontSize: 11.5, color: AP.ink2 }}>Dominant · <b style={{ color: AP.ink, fontWeight: 600 }}>{p.dominant}</b></span>}
          {p.temperature != null && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
              <Eyebrow>Cool</Eyebrow>
              <span style={{ width: 60, height: 4, borderRadius: 99, background: 'linear-gradient(90deg,#6f8fd9,#e8c07d,#c4633f)', position: 'relative' }}>
                <span style={{ position: 'absolute', top: -2, left: `${Math.round(((p.temperature + 1) / 2) * 100)}%`, width: 8, height: 8, borderRadius: 99, background: '#fff', boxShadow: `0 0 0 2px ${AP.card}` }} />
              </span>
              <Eyebrow>Warm</Eyebrow>
            </span>
          )}
        </div>
      </div>
    ) : <Muted>No palette extracted.</Muted>;
  }
  if (o.output_type === 'open_vocab_detections') {
    const queries = p.queries || [];
    const rows = aggregateDetections(p.detections);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {queries.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <Eyebrow>Configured to find</Eyebrow>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {queries.map((q) => (
                <span key={q} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: AP.lumenBg, border: `1px solid ${AP.lumenLine}`, borderRadius: 999, padding: '3px 9px 3px 8px', fontFamily: AP.sans, fontSize: 12, fontWeight: 500, color: AP.lumenSoft }}>
                  {q}
                </span>
              ))}
            </div>
          </div>
        )}
        {rows.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {rows.map((r) => (
              <ObjRow key={r.name} name={r.name} n={r.n} c={r.c} task={o.model_name} />
            ))}
          </div>
        ) : <Muted>None of the configured terms were found.</Muted>}
      </div>
    );
  }
  if (o.output_type === 'segments') {
    const segs = (p.segments || []).slice().sort((a, b) => b.area_fraction - a.area_fraction);
    return segs.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <span style={{ display: 'flex', width: '100%', height: 14, borderRadius: 7, overflow: 'hidden' }}>
          {segs.map((s) => (
            <span key={s.label} style={{ width: `${Math.round(s.area_fraction * 100)}%`, background: objColor(o.model_name, s.label) }} />
          ))}
        </span>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {segs.map((s) => (
            <span key={s.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: AP.sans, fontSize: 12, color: AP.ink2 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: objColor(o.model_name, s.label) }} />
              {s.label} · {Math.round(s.area_fraction * 100)}%
            </span>
          ))}
        </div>
      </div>
    ) : <Muted>No segments recorded.</Muted>;
  }
  if (o.output_type === 'annotations') {
    const fields = p.fields || {};
    const entries = Object.entries(fields);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {p.source === 'api' && <OffDeviceBadge provider={p.provider} />}
        {entries.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: '84px 1fr', gap: '8px 12px' }}>
            {entries.map(([key, value]) => (
              <React.Fragment key={key}>
                <Eyebrow>{key}</Eyebrow>
                {Array.isArray(value) ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {value.map((v, i) => (
                      <span key={i} style={{ display: 'inline-flex', alignItems: 'center', background: 'rgba(255,255,255,0.04)', border: `1px solid ${AP.line2}`, borderRadius: 999, padding: '3px 9px', fontFamily: AP.sans, fontSize: 12, color: AP.ink2 }}>
                        {String(v)}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span style={{ fontFamily: AP.sans, fontSize: 13, color: AP.ink }}>{String(value)}</span>
                )}
              </React.Fragment>
            ))}
          </div>
        ) : <Muted>No fields returned.</Muted>}
      </div>
    );
  }
  if (o.output_type === 'species') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
          <span style={{ fontFamily: AP.sans, fontSize: 17, fontWeight: 600, color: AP.ink, fontStyle: 'italic' }}>{p.name || 'Unidentified'}</span>
          {p.confidence != null && <Meter v={p.confidence} />}
        </div>
        {p.taxonomy?.length > 0 && (
          <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3, letterSpacing: '.01em' }}>{p.taxonomy.join(' › ')}</span>
        )}
      </div>
    );
  }
  if (o.output_type === 'scene') {
    const labels = p.labels || [];
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontFamily: AP.sans, fontSize: 13.5, color: AP.ink }}>
            {labels.map((l) => l.label).join(', ') || 'No scene labels'}
          </span>
          {p.indoor_outdoor && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: STATUS.ok.bg, border: `1px solid ${STATUS.ok.line}`, borderRadius: 999, padding: '2px 9px 2px 8px' }}>
              <span style={{ width: 6, height: 6, borderRadius: 99, background: STATUS.ok.c }} />
              <span style={{ fontFamily: AP.sans, fontSize: 11, fontWeight: 500, color: STATUS.ok.c, textTransform: 'capitalize' }}>{p.indoor_outdoor}</span>
            </span>
          )}
        </div>
        {p.attributes?.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {p.attributes.map((a) => (
              <span key={a} style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3, border: `1px solid ${AP.line2}`, borderRadius: 999, padding: '2px 8px' }}>{a}</span>
            ))}
          </div>
        )}
      </div>
    );
  }
  if (o.output_type === 'geo_estimate') {
    const candidates = p.candidates || [];
    return candidates.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {candidates.slice(0, 3).map((cand, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', opacity: i === 0 ? 1 : 0.6 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <GeoGlyph />
              <span style={{ fontFamily: AP.sans, fontSize: 12.5, color: AP.ink2 }}>{cand.region}</span>
            </span>
            <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>{cand.confidence?.toFixed(2)}</span>
          </div>
        ))}
      </div>
    ) : <Muted>No location estimate.</Muted>;
  }
  if (o.output_type === 'depth') {
    const marker = Math.round(Math.min(Math.max(p.median ?? 0.5, 0), 1) * 100);
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <Eyebrow>Depth</Eyebrow>
        <span style={{ flex: 1, height: 8, borderRadius: 99, background: 'linear-gradient(90deg,#3a3f57,#8b7bf7,#f3d9b1)', position: 'relative' }}>
          <span style={{ position: 'absolute', top: -2, left: `${marker}%`, width: 5, height: 12, borderRadius: 2, background: '#fff', boxShadow: `0 0 0 2px ${AP.card}` }} />
        </span>
        <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3, whiteSpace: 'nowrap' }}>near → far</span>
      </div>
    );
  }
  return <Muted>{o.summary || 'Output recorded.'}</Muted>;
}

// Small, deliberately plain pin glyph for the geo/location card — not a full
// map (nothing here is precise enough to earn one), just enough to read as
// "place" at a glance.
function GeoGlyph({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 21s-6-5.7-6-10.5A6 6 0 0 1 18 10.5C18 15.3 12 21 12 21z" stroke={AP.ink3} strokeWidth="1.7" />
      <circle cx="12" cy="10.3" r="1.9" stroke={AP.ink3} strokeWidth="1.7" />
    </svg>
  );
}

// Small badge marking a stage that sent the image to a third-party API
// (Claude, Google Cloud Vision, ...) rather than running locally — so a
// viewer scanning the page can tell at a glance which stages left the
// machine. `provider` defaults to a generic label when the payload doesn't
// carry one.
export function OffDeviceBadge({ provider }) {
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '3px 9px 3px 7px', borderRadius: 999,
        background: 'rgba(255,255,255,0.04)', border: `1px solid ${AP.line2}`,
        fontFamily: AP.mono, fontSize: 10, color: AP.ink2, whiteSpace: 'nowrap',
        alignSelf: 'flex-start',
      }}
    >
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
        <path d="M7 16a4.5 4.5 0 0 1-.5-8.98A6 6 0 0 1 18 8.5 4 4 0 0 1 17.5 16H7z" stroke="currentColor" strokeWidth="2" />
        <path d="M12 12v6M9.5 14.5 12 12l2.5 2.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      via {provider || 'external API'}
    </span>
  );
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
function ImageStatsIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 20V10M10 20V4M16 20v-7M22 20V8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
function AestheticIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3.5l2.47 5.6 6.03.55-4.58 4.06 1.36 5.9L12 16.7l-5.28 2.9 1.36-5.9-4.58-4.05 6.03-.56L12 3.5z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}
function FlagIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3 2 20h20L12 3z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M12 10v4M12 17h.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
function PaletteIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="8.5" cy="9.5" r="1.3" fill="currentColor" stroke="none" />
      <circle cx="15" cy="8.5" r="1.3" fill="currentColor" stroke="none" />
      <circle cx="16" cy="14.5" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  );
}
function SegmentsIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.7" />
      <path d="M3 14h18M11 3v11" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}
function AnnotationsIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}
function SpeciesIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 21s-7-5.2-7-11a7 7 0 0 1 14 0c0 5.8-7 11-7 11z" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="10" r="2.2" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}
function SceneIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M3 18l5-6 4 4 4-7 5 9" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  );
}
function GeoIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 21s-6-5.7-6-10.5A6 6 0 0 1 18 10.5C18 15.3 12 21 12 21z" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="10.3" r="1.9" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}
function DepthIcon({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M3 12c2.5-5 5.5-8 9-8s6.5 3 9 8c-2.5 5-5.5 8-9 8s-6.5-3-9-8z" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="2.6" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}
const OUTPUT_ICON = {
  detections: DetectionsIcon,
  labels: ClassificationIcon,
  caption: CaptionIcon,
  ocr: OcrIcon,
  written_image: WrittenImageIcon,
  image_stats: ImageStatsIcon,
  aesthetic_score: AestheticIcon,
  nsfw_flag: FlagIcon,
  color_palette: PaletteIcon,
  open_vocab_detections: DetectionsIcon,
  segments: SegmentsIcon,
  annotations: AnnotationsIcon,
  species: SpeciesIcon,
  scene: SceneIcon,
  geo_estimate: GeoIcon,
  depth: DepthIcon,
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
