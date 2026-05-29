import React, {
  useEffect, useLayoutEffect, useRef, useState, useCallback,
} from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';

const API = 'http://localhost:8000';

const labelColor = (label) => {
  const hash = label.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return `hsl(${hash % 360}, 72%, 62%)`;
};

/* ─────────────────────────────────────────────────────────────────────────
 * DetectionOverlay — SVG pinned via position:fixed to the rendered image rect.
 *
 * bbox format: [cx, cy, w, h]  in source-image pixel space.
 *
 * Mapping:
 *   normX = cx / natW          → 0..1 fraction of source width
 *   svgX  = (normX - nw/2) * renderedW   → pixel inside the rendered rect
 *
 * Hover state is tracked here so both the box AND the sidebar row can react.
 * ───────────────────────────────────────────────────────────────────────*/
function DetectionOverlay({
  imgRef, naturalW, naturalH, detections, visible, zoom,
  hoveredIdx, setHoveredIdx,
}) {
  const [rect, setRect] = useState(null);

  const measure = useCallback(() => {
    if (!imgRef.current) return;
    // Use offsetWidth/offsetHeight + offsetLeft/offsetTop so the SVG is
    // positioned relative to the nearest `position:relative` ancestor —
    // it moves with the image and is never affected by page/container scroll.
    setRect({
      w:    imgRef.current.offsetWidth,
      h:    imgRef.current.offsetHeight,
      top:  imgRef.current.offsetTop,
      left: imgRef.current.offsetLeft,
    });
  }, [imgRef]);

  useLayoutEffect(() => {
    measure();
    const ro = new ResizeObserver(measure);
    if (imgRef.current) ro.observe(imgRef.current);
    window.addEventListener('resize', measure);
    return () => { ro.disconnect(); window.removeEventListener('resize', measure); };
  }, [measure, imgRef, zoom]);

  // Still render if a sidebar row is hovered (hoveredIdx set) even when boxes toggled off
  if ((!visible && hoveredIdx === null) || !rect || naturalW === 0 || naturalH === 0) return null;

  const strokeBase = Math.max(1.5, rect.w * 0.0025);
  const fontBase   = Math.max(10, Math.min(14, rect.w * 0.022));
  const pad        = 3;

  return (
    <svg
      style={{
        position: 'absolute',          // ← relative to the wrapper div, not viewport
        left: rect.left,
        top:  rect.top,
        width:  rect.w,
        height: rect.h,
        pointerEvents: 'auto',
        zIndex: 20,
        overflow: 'visible',
      }}
    >
      {detections.map((det, i) => {
        const [cx, cy, bw, bh] = det.bbox;
        const nx = cx / naturalW,  ny = cy / naturalH;
        const nw = bw / naturalW,  nh = bh / naturalH;

        const rx = (nx - nw / 2) * rect.w;
        const ry = (ny - nh / 2) * rect.h;
        const rw = nw * rect.w;
        const rh = nh * rect.h;

        const color    = labelColor(det.label);
        const hovered  = hoveredIdx === i;
        const labelTxt = `${det.label} ${(det.confidence * 100).toFixed(0)}%`;
        const labelW   = labelTxt.length * fontBase * 0.58 + pad * 2;
        const labelH   = fontBase + pad * 2;
        const labelY   = ry >= labelH + 2 ? ry - labelH - 2 : ry + 2;
        const filterId = `glow-${i}`;

        return (
          <g key={i}>

            {/* ── Glow filter (hover only) ── */}
            <defs>
              <filter id={filterId} x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="5" result="blur" />
                <feFlood floodColor={color} floodOpacity="0.6" result="clr" />
                <feComposite in="clr" in2="blur" operator="in" result="glow" />
                <feMerge>
                  <feMergeNode in="glow" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/*
              ── Invisible hit-area ──────────────────────────────────────────
              Covers the entire bbox interior with pointer-events="all" so fast
              mouse movement across thin borders is still captured. This must
              come FIRST so it sits below the visible elements in z-order.
            */}
            <rect
              x={rx} y={ry} width={rw} height={rh}
              fill="transparent"
              stroke="none"
              style={{ pointerEvents: 'all', cursor: 'pointer' }}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
            />

            {/* ── Highlight fill — light tint of the border color ── */}
            <rect
              x={rx} y={ry} width={rw} height={rh}
              fill={color}
              fillOpacity={hovered ? 0.18 : 0}
              stroke="none"
              style={{ transition: 'fill-opacity 0.15s', pointerEvents: 'none' }}
            />

            {/* ── Border ── */}
            <rect
              x={rx} y={ry} width={rw} height={rh}
              fill="none"
              stroke={color}
              strokeWidth={hovered ? strokeBase * 2.2 : strokeBase}
              filter={hovered ? `url(#${filterId})` : undefined}
              style={{ transition: 'stroke-width 0.15s', pointerEvents: 'none' }}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
            />

            {/* ── Label pill ── */}
            <rect
              x={rx} y={labelY}
              width={labelW} height={labelH}
              fill={color}
              fillOpacity={hovered ? 1 : 0.78}
              rx={3}
              style={{ pointerEvents: 'none' }}
            />
            <text
              x={rx + pad}
              y={labelY + labelH - pad - 1}
              fontSize={fontBase}
              fontWeight="700"
              fontFamily="ui-monospace, monospace"
              fill="#000"
              style={{ pointerEvents: 'none' }}
            >
              {labelTxt}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
function ImageDetails() {
  const { id } = useParams();
  const [data, setData]               = useState(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState('');
  const [showBoxes, setShowBoxes]     = useState(true);
  const [naturalSize, setNaturalSize] = useState({ w: 0, h: 0 });
  const [zoom, setZoom]               = useState(1.0);
  const [hoveredIdx, setHoveredIdx]   = useState(null);

  const imgRef      = useRef(null);
  const sidebarRef  = useRef(null);   // for scrolling to hovered detection row

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/images/${id}/detail`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => { setError('Failed to load image.'); setLoading(false); });
  }, [id]);

  // Scroll the sidebar detection row into view when hovered via canvas
  useEffect(() => {
    if (hoveredIdx === null || !sidebarRef.current) return;
    const row = sidebarRef.current.querySelector(`[data-det-idx="${hoveredIdx}"]`);
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [hoveredIdx]);

  const handleImgLoad = () => {
    if (imgRef.current) {
      setNaturalSize({ w: imgRef.current.naturalWidth, h: imgRef.current.naturalHeight });
    }
  };

  // Zoom controls
  const zoomIn  = () => setZoom(z => Math.min(4, +(z + 0.25).toFixed(2)));
  const zoomOut = () => setZoom(z => Math.max(0.25, +(z - 0.25).toFixed(2)));
  const zoomReset = () => setZoom(1);

  // Ctrl+scroll to zoom
  const handleWheel = useCallback((e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    setZoom(z => Math.min(4, Math.max(0.25, +(z + (e.deltaY < 0 ? 0.1 : -0.1)).toFixed(2))));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center" style={{ height: '100vh' }}>
      <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
    </div>
  );

  if (error || !data) return (
    <div className="flex flex-col items-center gap-4 py-24 text-center">
      <p className="text-red-400 text-sm">{error || 'Image not found.'}</p>
      <Link to="/search" className="text-violet-400 text-xs hover:underline">← Back</Link>
    </div>
  );

  const filename   = data.current_path?.split(/[\\/]/).pop() ?? 'Image';
  const detections = Array.isArray(data.detections) ? data.detections : [];
  const thumbSrc   = `${API}/images/${id}/thumbnail`;

  return (
    // Full viewport, nothing overflows
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#020617', overflow: 'hidden' }}>

      {/* ── Top bar ─────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 16px', borderBottom: '1px solid #1e293b',
        flexShrink: 0, background: '#0f172a',
      }}>
        <Link to="/search" style={{
          display: 'flex', alignItems: 'center', gap: 6,
          color: '#64748b', textDecoration: 'none', fontSize: 13,
        }}
          onMouseEnter={e => e.currentTarget.style.color = '#a78bfa'}
          onMouseLeave={e => e.currentTarget.style.color = '#64748b'}
        >
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </Link>
        <span style={{ color: '#334155', fontSize: 13 }}>/</span>
        <span style={{
          fontSize: 13, fontWeight: 600, color: '#cbd5e1',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          maxWidth: 400,
        }} title={data.current_path}>{filename}</span>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Zoom controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button onClick={zoomOut}
            style={zoomBtn} title="Zoom out (or Ctrl+scroll)">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
            </svg>
          </button>
          <button onClick={zoomReset}
            style={{ ...zoomBtn, minWidth: 46, fontFamily: 'monospace', fontSize: 12, fontWeight: 700 }}
            title="Reset zoom">
            {Math.round(zoom * 100)}%
          </button>
          <button onClick={zoomIn}
            style={zoomBtn} title="Zoom in (or Ctrl+scroll)">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
            </svg>
          </button>
          {detections.length > 0 && (
            <button onClick={() => setShowBoxes(v => !v)}
              style={{
                ...zoomBtn,
                color: showBoxes ? '#a78bfa' : '#64748b',
                borderColor: showBoxes ? 'rgba(139,92,246,0.5)' : '#334155',
                background: showBoxes ? 'rgba(139,92,246,0.12)' : 'transparent',
              }}
              title="Toggle detection boxes">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              <span style={{ fontSize: 11, fontWeight: 700 }}>Boxes</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Body ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Sidebar ─────────────────────────────────────────────── */}
        <div ref={sidebarRef}
             style={{
               width: 260, flexShrink: 0,
               borderRight: '1px solid #1e293b',
               background: '#0f172a',
               overflowY: 'auto', overflowX: 'hidden',
               scrollbarWidth: 'thin', scrollbarColor: '#4c1d95 transparent',
             }}>

          {/* File info */}
          <Section label="File">
            <p style={valueStyle}>{filename}</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', marginTop: 4 }}>
              {data.size_bytes && <span style={metaStyle}>{(data.size_bytes / 1024).toFixed(1)} KB</span>}
              {naturalSize.w > 0 && <span style={metaStyle}>{naturalSize.w} × {naturalSize.h}</span>}
              {data.mime_type && <span style={{ ...metaStyle, color: '#475569' }}>{data.mime_type}</span>}
            </div>
            {data.latest_seen_at && (
              <p style={{ ...metaStyle, marginTop: 4 }}>{new Date(data.latest_seen_at).toLocaleString()}</p>
            )}
          </Section>

          {/* Caption */}
          <Section label="Caption">
            {data.description
              ? <p style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.55 }}>{data.description}</p>
              : <p style={{ fontSize: 12, color: '#334155', fontStyle: 'italic' }}>No caption yet</p>}
          </Section>

          {/* Detections */}
          <Section label={`Detections${detections.length ? ` (${detections.length})` : ''}`}>
            {detections.length === 0
              ? <p style={{ fontSize: 12, color: '#334155', fontStyle: 'italic' }}>None detected</p>
              : detections.map((det, i) => {
                  const color   = labelColor(det.label);
                  const active  = hoveredIdx === i;
                  return (
                    <div key={i}
                         data-det-idx={i}
                         onMouseEnter={() => setHoveredIdx(i)}
                         onMouseLeave={() => setHoveredIdx(null)}
                         style={{
                           display: 'flex', alignItems: 'center', gap: 8,
                           padding: '7px 10px', borderRadius: 8, marginBottom: 3,
                           background: active ? `${color}1a` : 'transparent',
                           border: `1px solid ${active ? color + '70' : '#1e293b'}`,
                           cursor: 'pointer', transition: 'all 0.13s',
                           boxShadow: active ? `inset 0 0 0 1px ${color}30` : 'none',
                         }}>
                      <span style={{
                        width: 11, height: 11, borderRadius: 3, flexShrink: 0,
                        background: color,
                        boxShadow: active ? `0 0 8px ${color}` : 'none',
                        transition: 'box-shadow 0.13s',
                      }} />
                      <span style={{
                        flex: 1, fontSize: 12, fontWeight: 600,
                        color: active ? '#f1f5f9' : '#94a3b8',
                        textTransform: 'capitalize', transition: 'color 0.13s',
                      }}>{det.label}</span>
                      <span style={{
                        fontSize: 11, color: active ? color : '#64748b',
                        fontVariantNumeric: 'tabular-nums', fontWeight: active ? 700 : 400,
                        transition: 'color 0.13s',
                      }}>
                        {(det.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
          </Section>

          {/* Path */}
          <Section label="Path">
            <p style={{ fontSize: 11, color: '#475569', fontFamily: 'monospace', wordBreak: 'break-all', lineHeight: 1.5 }}>
              {data.current_path}
            </p>
          </Section>
        </div>

        {/* ── Image canvas — NO scroll, image fills the space ─────── */}
        <div
          onWheel={handleWheel}
          style={{
            flex: 1,
            overflow: 'hidden',           // ← no scroll
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#020617',
            position: 'relative',
          }}
        >
          <img
            ref={imgRef}
            src={thumbSrc}
            alt={filename}
            onLoad={handleImgLoad}
            style={{
              // Fill available space while respecting aspect ratio
              maxWidth:  zoom === 1 ? '100%'  : 'none',
              maxHeight: zoom === 1 ? '100%'  : 'none',
              width:     zoom !== 1 ? `${zoom * 100}%` : undefined,
              display: 'block',
              borderRadius: 8,
              boxShadow: '0 8px 48px rgba(0,0,0,0.7)',
              transformOrigin: 'center center',
              transition: 'width 0.15s ease, max-width 0.15s ease, max-height 0.15s ease',
              userSelect: 'none',
            }}
          />

          <DetectionOverlay
            imgRef={imgRef}
            naturalW={naturalSize.w}
            naturalH={naturalSize.h}
            detections={detections}
            visible={showBoxes}
            zoom={zoom}
            hoveredIdx={hoveredIdx}
            setHoveredIdx={setHoveredIdx}
          />

          {/* Zoom hint */}
          <div style={{
            position: 'absolute', bottom: 12, right: 12,
            fontSize: 10, color: '#1e293b',
            pointerEvents: 'none', userSelect: 'none',
          }}>
            Ctrl + scroll to zoom
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Tiny helpers ─────────────────────────────────────────────────── */
function Section({ label, children }) {
  return (
    <div style={{ padding: '14px 16px', borderBottom: '1px solid #1e293b' }}>
      <p style={{
        fontSize: 9, fontWeight: 800, color: '#475569',
        textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8,
      }}>{label}</p>
      {children}
    </div>
  );
}

const valueStyle = { fontSize: 12, fontWeight: 600, color: '#e2e8f0', wordBreak: 'break-all' };
const metaStyle  = { fontSize: 11, color: '#64748b' };
const zoomBtn    = {
  display: 'flex', alignItems: 'center', gap: 4,
  padding: '4px 10px', borderRadius: 8,
  border: '1px solid #334155', background: 'transparent',
  color: '#94a3b8', cursor: 'pointer', fontSize: 12,
  transition: 'all 0.12s',
};

export default ImageDetails;
