// ImageDetails — Aperture hi-fi Image Detail, "Split" variant.
// Left: large image (full height, detection overlay). Right rail: FILE INFO (always)
// + PIPELINE OUTPUTS grouped by the pipeline section that produced them, each
// independently toggled on/off.
import React, { useState, useEffect, useMemo, useRef } from 'react';
import axios from 'axios';
import { useParams, useNavigate } from 'react-router-dom';
import { AP, Dot, Eyebrow, GhostBtn, LumenBtn, Toggle } from '../aperture/kit';

const API = 'http://localhost:8000';

/* ── small pieces ─────────────────────────────────────────────── */

function Meter({ v }) {
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

function ObjRow({ name, n, c }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span style={{ width: 9, height: 9, borderRadius: 2, border: `1.5px solid ${AP.lumen}`, flex: '0 0 auto' }} />
        <span style={{ fontFamily: AP.sans, fontSize: 13.5, color: AP.ink, whiteSpace: 'nowrap' }}>
          {name}
          {n > 1 ? <span style={{ color: AP.ink3 }}> ×{n}</span> : ''}
        </span>
      </span>
      <Meter v={c} />
    </div>
  );
}

const Muted = ({ children }) => (
  <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 12, color: AP.ink3, lineHeight: 1.5 }}>{children}</p>
);

const OUTPUT_LABEL = {
  caption: 'Caption',
  detections: 'Detections',
  labels: 'Classification',
  metadata: 'Metadata (EXIF)',
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

// Render one output's payload by type (the API now exposes payloads + a summary).
function OutputBody({ o }) {
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
        {rows.map((r) => <ObjRow key={r.name} name={r.name} n={r.n} c={r.c} />)}
      </div>
    ) : <Muted>No objects detected.</Muted>;
  }
  if (o.output_type === 'labels') {
    const labels = p.labels || [];
    return labels.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        {labels.map((l, i) => <ObjRow key={i} name={l.label} n={1} c={l.confidence ?? 0} />)}
      </div>
    ) : <Muted>No labels.</Muted>;
  }
  if (o.output_type === 'metadata') {
    const entries = Object.entries(p.metadata || {});
    return entries.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {entries.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
            <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>{k}</span>
            <span
              style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink, textAlign: 'right', maxWidth: '62%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              title={String(v)}
            >
              {String(v)}
            </span>
          </div>
        ))}
      </div>
    ) : <Muted>Dimensions only — no EXIF.</Muted>;
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

function OutputCard({ o }) {
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
      <OutputBody o={o} />
    </div>
  );
}

function PipelineSection({ section, on, toggle, children }) {
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
          <div style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3, paddingLeft: 20, marginTop: 3 }}>
            {section.task} · {section.model}
          </div>
        </div>
        <Toggle on={on} onClick={toggle} />
      </div>
      {on && <div style={{ paddingTop: 13, paddingLeft: 20 }}>{children}</div>}
    </div>
  );
}

/* ── detection overlay ────────────────────────────────────────── */

function DetectionOverlay({ detections, naturalW, naturalH }) {
  if (!naturalW || !naturalH || !detections.length) return null;
  return (
    <svg
      viewBox={`0 0 ${naturalW} ${naturalH}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 2 }}
    >
      {detections.map((det, i) => {
        if (!Array.isArray(det.bbox) || det.bbox.length !== 4) return null;
        const [cx, cy, bw, bh] = det.bbox;
        const x = cx - bw / 2;
        const y = cy - bh / 2;
        const stroke = Math.max(2, naturalW / 500);
        const fs = Math.max(12, naturalW / 60);
        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={bw}
              height={bh}
              fill="rgba(139,123,247,.08)"
              stroke={AP.lumen}
              strokeWidth={stroke}
              rx={4}
            />
            <text
              x={x + stroke * 2}
              y={Math.max(y - stroke * 2, fs)}
              fill={AP.lumenSoft}
              fontSize={fs}
              fontFamily={AP.mono}
            >
              {det.label} {(det.confidence * 100).toFixed(0)}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ── main ─────────────────────────────────────────────────────── */

export default function ImageDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [enabled, setEnabled] = useState({});
  const [copied, setCopied] = useState(false);
  const [naturalDims, setNaturalDims] = useState({ w: 0, h: 0 });
  const imgRef = useRef(null);

  useEffect(() => {
    axios
      .get(`${API}/images/${id}/detail`)
      .then((r) => setData(r.data))
      .catch(() => setError('Could not load image details.'));
  }, [id]);

  // Outputs are grouped by the pipeline that produced them (provenance.pipelines).
  const pipelines = useMemo(() => data?.provenance?.pipelines ?? [], [data]);

  useEffect(() => {
    setEnabled(Object.fromEntries(pipelines.map((p) => [p.pipeline_id ?? '_default', true])));
  }, [pipelines]);

  if (error) {
    return (
      <div style={{ padding: 40, fontFamily: AP.sans, color: '#f0566b', fontSize: 14 }}>
        {error}{' '}
        <button
          onClick={() => navigate(-1)}
          style={{ color: AP.lumenSoft, background: 'none', border: 'none', cursor: 'pointer' }}
        >
          ‹ Go back
        </button>
      </div>
    );
  }
  if (!data) {
    return <div style={{ padding: 40, fontFamily: AP.mono, color: AP.ink3, fontSize: 13 }}>loading…</div>;
  }

  const filename = data.current_path?.split(/[\\/]/).pop() ?? 'image';
  const meta = data.metadata || {};
  const dimsFromMeta = meta.width && meta.height ? `${meta.width} × ${meta.height}` : null;
  const dims = dimsFromMeta || (naturalDims.w ? `${naturalDims.w} × ${naturalDims.h}` : '—');
  const sizeStr = data.size_bytes
    ? data.size_bytes > 1024 * 1024
      ? `${(data.size_bytes / 1024 / 1024).toFixed(1)} MB`
      : `${(data.size_bytes / 1024).toFixed(1)} KB`
    : '—';
  const mime = (data.mime_type || '').split('/').pop()?.toUpperCase() || '';
  const added = data.first_seen_at ? new Date(data.first_seen_at).toLocaleString() : '—';
  const detections = Array.isArray(data.detections) ? data.detections : [];
  // Overlay boxes when any enabled pipeline produced detections.
  const detectionKeys = pipelines
    .filter((p) => (p.outputs ?? []).some((o) => o.output_type === 'detections'))
    .map((p) => p.pipeline_id ?? '_default');
  const showBoxes = detectionKeys.some((k) => enabled[k]);
  const onCount = pipelines.filter((p) => enabled[p.pipeline_id ?? '_default']).length;

  const fileInfo = [
    ['path', data.current_path ?? '—'],
    ['id', data._id],
    ['dims', dims],
    ['size', `${sizeStr}${mime ? ` · ${mime}` : ''}`],
    ['added', added],
  ];

  const copyId = () => {
    navigator.clipboard?.writeText(data._id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    });
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', color: AP.ink, overflow: 'hidden' }}>
      {/* top bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          padding: '13px 20px',
          borderBottom: `1px solid ${AP.line}`,
          background: AP.panel,
          flex: '0 0 auto',
        }}
      >
        <button
          onClick={() => navigate(-1)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            cursor: 'pointer',
            background: 'transparent',
            border: 'none',
            fontFamily: AP.sans,
            fontSize: 14,
            fontWeight: 500,
            color: AP.ink2,
          }}
        >
          <span style={{ fontSize: 15 }}>‹</span> Back
        </button>
        <div style={{ width: 1, height: 18, background: AP.line2 }} />
        <span
          style={{
            fontFamily: AP.mono,
            fontSize: 12,
            color: AP.ink3,
            flex: 1,
            minWidth: 0,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
          title={data.current_path}
        >
          {data.current_path}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <GhostBtn onClick={() => window.open(`${API}/images/${id}/thumbnail`, '_blank')}>↗ Open</GhostBtn>
          <GhostBtn onClick={copyId}>{copied ? '✓ Copied' : '⧉ Copy id'}</GhostBtn>
          <LumenBtn disabled title="Needs a similar-image endpoint on the backend — not available yet">
            ✦ Find similar
          </LumenBtn>
        </div>
      </div>

      {/* split body */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* image */}
        <div style={{ flex: 1, minWidth: 0, padding: 20, display: 'flex' }}>
          <div
            className="ap-photo"
            style={{
              flex: 1,
              borderRadius: 16,
              background: AP.cardHi,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <img
              ref={imgRef}
              src={`${API}/images/${id}/thumbnail`}
              alt={filename}
              onLoad={(e) => setNaturalDims({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain' }}
            />
            {showBoxes && (
              <DetectionOverlay detections={detections} naturalW={naturalDims.w} naturalH={naturalDims.h} />
            )}
            <span className="ap-vig" />
            <div
              style={{
                position: 'absolute',
                left: 16,
                bottom: 14,
                zIndex: 3,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 9,
                background: 'rgba(8,9,15,.55)',
                backdropFilter: 'blur(10px)',
                WebkitBackdropFilter: 'blur(10px)',
                border: '1px solid rgba(255,255,255,.14)',
                borderRadius: 10,
                padding: '7px 12px',
              }}
            >
              <span style={{ fontFamily: AP.mono, fontSize: 12, color: '#fff' }}>{filename}</span>
              <span style={{ fontFamily: AP.mono, fontSize: 11, color: 'rgba(255,255,255,.6)' }}>{dims}</span>
            </div>
          </div>
        </div>

        {/* info rail */}
        <div
          className="ap-scroll"
          style={{
            width: 360,
            flex: '0 0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 18,
            padding: 20,
            borderLeft: `1px solid ${AP.line}`,
            overflowY: 'auto',
          }}
        >
          {/* FILE INFO — always shown */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 13 }}>
              <Dot c={AP.ink3} size={6} />
              <Eyebrow>File info · always shown</Eyebrow>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {fileInfo.map(([k, v]) => (
                <div
                  key={k}
                  style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}
                >
                  <span style={{ fontFamily: AP.mono, fontSize: 11.5, color: AP.ink3 }}>{k}</span>
                  <span
                    style={{
                      fontFamily: AP.mono,
                      fontSize: 11.5,
                      color: AP.ink,
                      textAlign: 'right',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      maxWidth: '68%',
                    }}
                    title={String(v)}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ height: 1, background: AP.line }} />

          {/* PIPELINE OUTPUTS */}
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                marginBottom: 13,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{ fontSize: 12, color: AP.lumen }}>✦</span>
                <Eyebrow c={AP.lumenSoft}>Pipeline outputs</Eyebrow>
              </div>
              <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>
                {onCount}/{pipelines.length} shown
              </span>
            </div>

            {pipelines.length === 0 ? (
              <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3, lineHeight: 1.5 }}>
                No pipeline outputs yet — this image may still be queued for processing.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {pipelines.map((p) => {
                  const key = p.pipeline_id ?? '_default';
                  const outputs = p.outputs ?? [];
                  return (
                    <PipelineSection
                      key={key}
                      section={{
                        name: p.name,
                        id: p.pipeline_id ? String(p.pipeline_id).slice(0, 8) : null,
                        task: p.status || 'pipeline',
                        model: `${outputs.length} output${outputs.length === 1 ? '' : 's'}`,
                      }}
                      on={!!enabled[key]}
                      toggle={() => setEnabled((e) => ({ ...e, [key]: !e[key] }))}
                    >
                      {outputs.length ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                          {outputs.map((o, i) => (
                            <OutputCard key={`${o.output_type}-${o.order ?? i}`} o={o} />
                          ))}
                        </div>
                      ) : (
                        <Muted>This pipeline produced no outputs (it may have failed).</Muted>
                      )}
                    </PipelineSection>
                  );
                })}
              </div>
            )}
          </div>

          <div
            style={{
              marginTop: 'auto',
              display: 'flex',
              gap: 7,
              alignItems: 'flex-start',
              paddingTop: 6,
              color: AP.ink3,
            }}
          >
            <span style={{ color: AP.lumen, fontSize: 12, flex: '0 0 auto' }}>✦</span>
            <span style={{ fontFamily: AP.sans, fontSize: 12, lineHeight: 1.45 }}>
              Outputs are grouped by the pipeline that produced them — two pipelines can run the same task with
              different models.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
