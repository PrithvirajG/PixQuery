// ImageDetails — Aperture hi-fi Image Detail, "Split" variant.
// Left: large image (full height, detection overlay). Right rail: FILE INFO (always)
// + PIPELINE OUTPUTS grouped by the pipeline section that produced them, each
// independently toggled on/off.
import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import axios from 'axios';
import { useParams, useNavigate } from 'react-router-dom';
import { AP, STATUS, Dot, Eyebrow, GhostBtn, LumenBtn, ShimmerCard } from '../aperture/kit';
import { IN_FLIGHT, Muted, OutputBody, StageCard, PipelineSection, objColor, outputLabel, outputIcon } from '../aperture/blocks';
import { API_BASE as API } from '../lib/apiBase';
import { errorMessage } from '../lib/apiError';
import { subscribeToEvents } from '../lib/eventSocket';

// Friendly labels + formatters for EXIF fields shown in File Info, each only
// rendered when the underlying value is present on this particular image.
const EXIF_FIELDS = [
  ['camera', (m) => [m.camera_make, m.camera_model].filter(Boolean).join(' ') || null],
  ['captured', (m) => m.datetime_original || m.datetime || null],
  ['geo-location', (m) =>
    m.gps_latitude != null && m.gps_longitude != null
      ? `${m.gps_latitude.toFixed(5)}, ${m.gps_longitude.toFixed(5)}`
      : null],
  ['focal length', (m) => (m.focal_length != null ? `${Number(m.focal_length).toFixed(1)}mm` : null)],
  ['aperture', (m) => (m.f_number != null ? `f/${Number(m.f_number).toFixed(1)}` : null)],
  ['shutter', (m) => {
    if (m.exposure_time == null) return null;
    const s = Number(m.exposure_time);
    return s < 1 ? `1/${Math.round(1 / s)}s` : `${s.toFixed(1)}s`;
  }],
  ['iso', (m) => (m.iso != null ? String(Math.round(Number(m.iso))) : null)],
  ['lens', (m) => m.lens_model || null],
];

function buildExifRows(meta) {
  return EXIF_FIELDS.map(([label, get]) => [label, get(meta)]).filter(([, v]) => v);
}

/* ── detection overlay ────────────────────────────────────────── */

function DetectionOverlay({ detections, naturalW, naturalH, hiddenLabels, hoveredLabel }) {
  if (!naturalW || !naturalH || !detections.length) return null;
  const visible = detections.filter((det) => !hiddenLabels?.has(det.label));
  if (!visible.length) return null;
  // Draw the hovered label's boxes last so they sit on top of any overlap.
  const ordered = [...visible].sort(
    (a, b) => (a.label === hoveredLabel ? 1 : 0) - (b.label === hoveredLabel ? 1 : 0)
  );
  return (
    <svg
      viewBox={`0 0 ${naturalW} ${naturalH}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 2 }}
    >
      {ordered.map((det, i) => {
        if (!Array.isArray(det.bbox) || det.bbox.length !== 4) return null;
        const [cx, cy, bw, bh] = det.bbox;
        const x = cx - bw / 2;
        const y = cy - bh / 2;
        const isHovered = det.label === hoveredLabel;
        const stroke = Math.max(2, naturalW / 500) * (isHovered ? 1.6 : 1);
        const fs = Math.max(12, naturalW / 60);
        // Same colour function as ObjRow's swatch, keyed the same way (task +
        // label) — a box and its row always agree without hovering anything.
        // Hover stays the object's own hue, just heavier: swapping to a
        // different colour on hover would undercut the very thing this is for.
        const color = objColor(det.__task, det.label);
        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={bw}
              height={bh}
              fill={objColor(det.__task, det.label, isHovered ? 0.16 : 0.08)}
              stroke={color}
              strokeWidth={stroke}
              rx={4}
            />
            <text
              x={x + stroke * 2}
              y={Math.max(y - stroke * 2, fs)}
              fill={color}
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

/* ── resizable info rail ──────────────────────────────────────── */

const RAIL_WIDTH_KEY = 'pixquery_rail_width';
const RAIL_MIN = 280;
const RAIL_DEFAULT = 360;
// Leave at least this much room for the image, so the rail can never be dragged
// wide enough to swallow the thing the page is actually about.
const IMAGE_MIN = 360;

function railMax() {
  const viewport = typeof window === 'undefined' ? 1280 : window.innerWidth || 1280;
  return Math.max(RAIL_MIN, viewport - IMAGE_MIN);
}

function clampRailWidth(width) {
  return Math.round(Math.min(Math.max(width, RAIL_MIN), railMax()));
}

function readStoredRailWidth() {
  try {
    const stored = Number(localStorage.getItem(RAIL_WIDTH_KEY));
    if (Number.isFinite(stored) && stored > 0) return clampRailWidth(stored);
  } catch {
    // Storage unavailable — fall through to the default.
  }
  return RAIL_DEFAULT;
}

function ResizeHandle({ onMouseDown, onKeyDown, width }) {
  const [active, setActive] = useState(false);
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize info panel"
      aria-valuenow={width}
      aria-valuemin={RAIL_MIN}
      aria-valuemax={railMax()}
      tabIndex={0}
      onMouseDown={onMouseDown}
      onKeyDown={onKeyDown}
      onMouseEnter={() => setActive(true)}
      onMouseLeave={() => setActive(false)}
      onFocus={() => setActive(true)}
      onBlur={() => setActive(false)}
      style={{
        flex: '0 0 auto',
        width: 5,
        cursor: 'col-resize',
        // The visible line is the rail's border; this widens only the hit area.
        background: active ? AP.lumenLine : 'transparent',
        transition: 'background .12s',
        outline: 'none',
      }}
    />
  );
}

/* ── main ─────────────────────────────────────────────────────── */

export default function ImageDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [enabled, setEnabled] = useState({});
  const [hiddenStages, setHiddenStages] = useState(() => new Set());
  const [copied, setCopied] = useState(false);
  const [naturalDims, setNaturalDims] = useState({ w: 0, h: 0 });
  const [hiddenLabels, setHiddenLabels] = useState(() => new Set());
  const [hoveredLabel, setHoveredLabel] = useState(null);
  const [retriggering, setRetriggering] = useState({});
  const [deleting, setDeleting] = useState({});
  // Per-pipeline overrides applied on top of server data between refetches, so a
  // status pill flips the instant an event lands instead of after the round-trip.
  const [live, setLive] = useState({});
  const [connected, setConnected] = useState(false);
  const [railWidth, setRailWidth] = useState(readStoredRailWidth);
  const imgRef = useRef(null);
  const workspaceRef = useRef(null);
  const everConnected = useRef(false);

  const refetch = useCallback(
    () =>
      axios
        .get(`${API}/images/${id}/detail`)
        .then((r) => {
          setData(r.data);
          // Server data supersedes the optimistic overlay: every event that got us
          // here was emitted after its write, so what just arrived is at least as
          // fresh as anything we were holding.
          setLive({});
          return r.data;
        })
        .catch(() => {
          setError('Could not load image details.');
          return null;
        }),
    [id]
  );

  useEffect(() => {
    refetch();
    setHiddenLabels(new Set());
    setHoveredLabel(null);
    setLive({});
  }, [id, refetch]);

  // Outputs are grouped by the pipeline that produced them (provenance.pipelines).
  const pipelines = useMemo(() => data?.provenance?.pipelines ?? [], [data]);

  useEffect(() => {
    workspaceRef.current = data?.workspace_id ?? null;
  }, [data]);

  // Live updates. The socket only says *what changed*; anything substantive is
  // refetched, so a missed event costs a delay rather than showing stale outputs.
  useEffect(() => {
    const unsubscribe = subscribeToEvents((event) => {
      if (event.type === '_open') {
        setConnected(true);
        // Resync after a reconnect — we may have missed transitions while away.
        if (everConnected.current) refetch();
        everConnected.current = true;
        return;
      }
      if (event.type === '_close') {
        setConnected(false);
        return;
      }
      // An event naming a different image is not ours. One with no image at all
      // (a workspace-wide clear) applies only if it's this image's workspace.
      if (event.asset_id) {
        if (event.asset_id !== id) return;
      } else if (event.workspace_id && event.workspace_id !== workspaceRef.current) {
        return;
      }

      if (event.type === 'pipeline_state') {
        const pid = event.pipeline_id;
        setLive((prev) => ({
          ...prev,
          [pid]: { state: event.data?.state, error: event.data?.error, stage: null },
        }));
        // Terminal states are the ones that change what's on screen.
        if (event.data?.state === 'completed' || event.data?.state === 'failed') refetch();
      } else if (event.type === 'pipeline_stage') {
        const pid = event.pipeline_id;
        setLive((prev) => ({
          ...prev,
          [pid]: { ...(prev[pid] || {}), state: prev[pid]?.state || 'processing', stage: event.data },
        }));
      } else if (event.type === 'outputs_cleared') {
        refetch();
      }
    });
    return unsubscribe;
  }, [id, refetch]);

  // Effective per-pipeline view: server truth, with any live override on top.
  const viewPipelines = useMemo(
    () =>
      pipelines.map((p) => {
        const override = live[p.pipeline_id] || {};
        const state = override.state || p.state || 'not_started';
        return {
          ...p,
          state,
          stage: override.stage || null,
          // A pipeline mid-run has had its previous outputs deleted already, so
          // whatever we're still holding is stale — don't render it as current.
          outputs: IN_FLIGHT.has(state) ? [] : p.outputs ?? [],
          staleOutputCount: (p.outputs ?? []).length,
          last_error: override.error || p.last_error,
        };
      }),
    [pipelines, live]
  );

  // Fallback polling — only when the socket is down AND something is in flight,
  // so a broker outage degrades to the old behaviour instead of freezing the UI.
  const anyInFlight = viewPipelines.some((p) => IN_FLIGHT.has(p.state));
  useEffect(() => {
    if (connected || !anyInFlight) return undefined;
    const timer = setInterval(refetch, 4000);
    return () => clearInterval(timer);
  }, [connected, anyInFlight, refetch]);

  useEffect(() => {
    try {
      localStorage.setItem(RAIL_WIDTH_KEY, String(railWidth));
    } catch {
      // Private mode / blocked storage: the width just won't persist.
    }
  }, [railWidth]);

  const resizeRail = useCallback((delta, from) => {
    setRailWidth(() => clampRailWidth(from + delta));
  }, []);

  const startResize = useCallback(
    (e) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = railWidth;
      // Dragging left (smaller clientX) widens the rail, hence the inversion.
      const onMove = (ev) => resizeRail(startX - ev.clientX, startWidth);
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
      // Held on <body> so the cursor doesn't flicker when the pointer outruns the
      // handle mid-drag, and so text elsewhere isn't selected.
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [railWidth, resizeRail]
  );

  const onResizeKey = useCallback(
    (e) => {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      const step = e.shiftKey ? 48 : 16;
      setRailWidth((w) => clampRailWidth(w + (e.key === 'ArrowLeft' ? step : -step)));
    },
    []
  );

  useEffect(() => {
    setEnabled(Object.fromEntries(pipelines.map((p) => [p.pipeline_id ?? '_default', true])));
  }, [pipelines]);

  const detectionState = useMemo(
    () => ({
      hiddenLabels,
      hoveredLabel,
      toggleLabel: (name) =>
        setHiddenLabels((prev) => {
          const next = new Set(prev);
          if (next.has(name)) next.delete(name);
          else next.add(name);
          return next;
        }),
      setHoveredLabel,
    }),
    [hiddenLabels, hoveredLabel]
  );

  // Run (or re-run) one pipeline against this image. The worker processes it
  // asynchronously and reports back over the event socket, so this only has to
  // dispatch the job — queued → processing → completed/failed arrives on its own.
  const retrigger = async (pipelineId) => {
    if (!pipelineId) return;
    setRetriggering((r) => ({ ...r, [pipelineId]: true }));
    try {
      await axios.post(`${API}/images/${id}/reprocess`, { pipeline_id: pipelineId });
      // Show "Queued" immediately rather than waiting for the event to round-trip.
      setLive((prev) => ({ ...prev, [pipelineId]: { state: 'queued', stage: null } }));
    } catch (err) {
      // Non-fatal: keep the page rendered, surface a dismissible notice.
      setActionError(errorMessage(err, 'Could not start processing for this pipeline.'));
    } finally {
      setRetriggering((r) => ({ ...r, [pipelineId]: false }));
    }
  };

  // Delete one pipeline's stored outputs for this image. Destructive and not
  // undoable, so it asks first — the pipeline can be re-run afterwards.
  const deleteOutputs = async (pipelineId, name) => {
    if (!pipelineId) return;
    const ok = window.confirm(
      `Delete every output “${name}” produced for this image?\n\n` +
        'This removes its detections, captions and other results and resets the ' +
        'pipeline to Not started. You can run it again afterwards.'
    );
    if (!ok) return;
    setDeleting((d) => ({ ...d, [pipelineId]: true }));
    try {
      await axios.delete(`${API}/images/${id}/outputs/${pipelineId}`);
      await refetch();
    } catch (err) {
      setActionError(errorMessage(err, 'Could not delete this pipeline’s outputs.'));
    } finally {
      setDeleting((d) => ({ ...d, [pipelineId]: false }));
    }
  };

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
  // Boxes are derived from the same per-pipeline outputs the rail renders, rather
  // than the flat `data.detections`, so toggling a pipeline off — or a pipeline
  // going in-flight, which empties its outputs — removes its boxes too.
  const detections = viewPipelines.flatMap((p) =>
    enabled[p.pipeline_id ?? '_default']
      ? (p.outputs ?? []).flatMap((o) =>
          o.output_type === 'detections'
            // __task carries the producing model into the overlay so its box
            // colour matches ObjRow's swatch for the same detection (objColor
            // is keyed by task + label, not label alone).
            ? (o.payload?.detections ?? []).map((d) => ({ ...d, __task: o.model_name }))
            : []
        )
      : []
  );
  const showBoxes = detections.length > 0;
  const onCount = viewPipelines.filter((p) => enabled[p.pipeline_id ?? '_default']).length;

  const fileInfo = [
    ['path', data.current_path ?? '—'],
    ['id', data._id],
    ['dims', dims],
    ['size', `${sizeStr}${mime ? ` · ${mime}` : ''}`],
    ['added', added],
    ...buildExifRows(meta),
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
              <DetectionOverlay
                detections={detections}
                naturalW={naturalDims.w}
                naturalH={naturalDims.h}
                hiddenLabels={hiddenLabels}
                hoveredLabel={hoveredLabel}
              />
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

        <ResizeHandle onMouseDown={startResize} onKeyDown={onResizeKey} width={railWidth} />

        {/* info rail */}
        <div
          className="ap-scroll"
          style={{
            width: railWidth,
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
                {/* Whether this page is receiving live updates. Worth surfacing:
                    it's the difference between "nothing is happening" and
                    "we can't see what's happening". */}
                <span
                  title={
                    connected
                      ? 'Live — updates arrive as the pipeline runs'
                      : 'Not connected — falling back to periodic refresh'
                  }
                  style={{ display: 'inline-flex', alignItems: 'center' }}
                >
                  <Dot c={connected ? STATUS.ok.c : AP.ink4} size={5} glow={connected} />
                </span>
              </div>
              <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>
                {onCount}/{viewPipelines.length} shown
              </span>
            </div>

            {actionError && (
              <div
                onClick={() => setActionError('')}
                title="Dismiss"
                style={{
                  marginBottom: 10,
                  padding: '8px 11px',
                  borderRadius: 9,
                  background: STATUS.err.bg,
                  border: `1px solid ${STATUS.err.line}`,
                  fontFamily: AP.sans,
                  fontSize: 12,
                  color: STATUS.err.c,
                  cursor: 'pointer',
                  lineHeight: 1.45,
                }}
              >
                {actionError}
              </div>
            )}

            {viewPipelines.length === 0 ? (
              <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3, lineHeight: 1.5 }}>
                No pipelines are attached to this image’s workspace — attach one from the workspace
                page to process this image.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {viewPipelines.map((p) => {
                  const key = p.pipeline_id ?? '_default';
                  const outputs = p.outputs ?? [];
                  const state = p.state;
                  const inFlight = IN_FLIGHT.has(state);
                  // Mirror the shape of whatever was there before, so the panel
                  // keeps its height while the run replaces it.
                  const skeletons = Math.min(Math.max(p.staleOutputCount, 1), 4);
                  return (
                    <PipelineSection
                      key={key}
                      section={{
                        name: p.name,
                        id: p.pipeline_id ? String(p.pipeline_id).slice(0, 8) : null,
                        state,
                        stage: p.stage,
                        detached: p.attached === false,
                        lastError: p.last_error?.message,
                        hasOutputs: p.staleOutputCount > 0,
                        model: inFlight
                          ? 'working…'
                          : `${outputs.length} output${outputs.length === 1 ? '' : 's'}`,
                      }}
                      on={!!enabled[key]}
                      toggle={() => setEnabled((e) => ({ ...e, [key]: !e[key] }))}
                      onProcess={p.pipeline_id && p.attached !== false ? () => retrigger(p.pipeline_id) : null}
                      processing={p.pipeline_id ? retriggering[p.pipeline_id] : false}
                      onDelete={p.pipeline_id ? () => deleteOutputs(p.pipeline_id, p.name) : null}
                      deleting={p.pipeline_id ? deleting[p.pipeline_id] : false}
                    >
                      {inFlight ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                          {Array.from({ length: skeletons }).map((_, i) => (
                            <ShimmerCard
                              key={i}
                              lines={2}
                              label={`${p.name} is ${state} — waiting for results`}
                            />
                          ))}
                        </div>
                      ) : outputs.length ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                          {outputs.map((o, i) => {
                            const stageKey = `${key}:${i}`;
                            return (
                              <StageCard
                                key={`${o.output_type}-${o.order ?? i}`}
                                index={i + 1}
                                total={outputs.length}
                                name={outputLabel(o)}
                                icon={outputIcon(o)}
                                trailing={o.model_name ? `${o.model_name}${o.model_version ? ` · ${o.model_version}` : ''}` : null}
                                hidden={hiddenStages.has(stageKey)}
                                onToggleHidden={() =>
                                  setHiddenStages((s) => {
                                    const next = new Set(s);
                                    if (next.has(stageKey)) next.delete(stageKey);
                                    else next.add(stageKey);
                                    return next;
                                  })
                                }
                              >
                                <OutputBody o={o} detectionState={detectionState} />
                              </StageCard>
                            );
                          })}
                        </div>
                      ) : (
                        <Muted>
                          {state === 'not_started'
                            ? 'Not processed yet — use Process to run this pipeline.'
                            : state === 'failed'
                              ? 'This run failed — no outputs were produced.'
                              : 'No outputs yet.'}
                        </Muted>
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
