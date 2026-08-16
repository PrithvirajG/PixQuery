// SearchView — Aperture hi-fi Search (Gallery). Grid + left filter rail, flat ranked
// grid with match-reason chips, and a grouped-by-reason mode.
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import axios from 'axios';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  AP,
  Dot,
  Kbd,
  MagIcon,
  LumenBtn,
  GhostBtn,
  Chip,
  Eyebrow,
  SelectControl,
  Photo,
} from '../aperture/kit';

const API = 'http://localhost:8000';
const PAGE_SIZE = 24;

const MODES = [
  { value: 'keyword', label: 'Keyword', desc: 'Match on file paths & captions' },
  { value: 'semantic', label: 'Semantic', desc: 'Vector search via CLIP embeddings' },
  { value: 'hybrid', label: 'Hybrid', desc: 'Keyword + semantic, re-ranked' },
];

const FIELD_LABELS = { filename: 'filename', caption: 'caption', ocr: 'image text' };

// Derive the match-reason chip label + score from the backend's match_reason payload.
function reasonFor(img) {
  const r = img.match_reason;
  if (!r) return null;
  const fields = (r.fields || []).map((f) => FIELD_LABELS[f] || f);
  const label = fields.length ? `in ${fields.join(' + ')}` : r.mode === 'semantic' ? 'visually similar' : r.mode;
  const score = typeof r.similarity === 'number' ? Math.round(r.similarity * 100) : null;
  return { label, score };
}

function ResultCell({ img, onOpen }) {
  const reason = reasonFor(img);
  const filename = img.current_path?.split(/[\\/]/).pop() ?? 'Image';
  return (
    <div className="ap-cell" style={{ cursor: 'pointer' }} onClick={onOpen} title={filename}>
      <Photo src={`${API}/images/${img._id}/thumbnail`} alt={filename} style={{ aspectRatio: '4 / 3' }} />
      <div style={{ marginTop: 9, display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
        {reason ? (
          <Chip reason={reason.label} score={reason.score} variant="pill" />
        ) : (
          <span
            style={{
              fontFamily: AP.mono,
              fontSize: 11,
              color: AP.ink3,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {filename}
          </span>
        )}
      </div>
    </div>
  );
}

function FacetPill({ children, onRemove, primary = false }) {
  return (
    <span
      className="ap-facet"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontFamily: AP.sans,
        fontSize: 12.5,
        fontWeight: 500,
        color: primary ? AP.ink : AP.ink2,
        padding: '4px 9px',
        borderRadius: 8,
        background: primary ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.03)',
        border: `1px solid ${primary ? AP.line2 : AP.line}`,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          style={{
            fontSize: 12,
            color: AP.ink3,
            lineHeight: 1,
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          ×
        </button>
      )}
    </span>
  );
}

function GroupHeader({ label, score, count, collapsed, onToggle }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        <Chip reason={label} score={score} variant="pill" />
        <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>
          {count} image{count === 1 ? '' : 's'}
        </span>
      </div>
      <button
        type="button"
        onClick={onToggle}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          cursor: 'pointer',
          background: 'transparent',
          border: 'none',
          fontFamily: AP.sans,
          fontSize: 12.5,
          color: AP.ink3,
          padding: '2px 4px',
        }}
      >
        {collapsed ? 'expand' : 'collapse'}
        <span style={{ fontSize: 10 }}>{collapsed ? '▾' : '▴'}</span>
      </button>
    </div>
  );
}

function ImageQueryView() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mode, setMode] = useState('keyword');
  const [threshold, setThreshold] = useState(0.0);
  const [workspaceId, setWsId] = useState(searchParams.get('workspace_id') ?? '');
  const [workspaces, setWorkspaces] = useState([]);
  const [wsMenuOpen, setWsMenuOpen] = useState(false);
  const [grouped, setGrouped] = useState(false);
  const [collapsed, setCollapsed] = useState({});
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/workspaces`).then((r) => setWorkspaces(r.data)).catch(() => {});
    inputRef.current?.focus();
  }, []);

  // ⌘K / Ctrl+K focuses the query field
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const fetchPage = useCallback(
    async (targetPage, opts = {}) => {
      const q = opts.query ?? query;
      const m = opts.mode ?? mode;
      const thr = opts.threshold ?? threshold;
      const ws = opts.workspaceId ?? workspaceId;

      setLoading(true);
      setError('');
      try {
        const params = new URLSearchParams({
          query: q.trim(),
          mode: m,
          top_k: PAGE_SIZE,
          skip: targetPage * PAGE_SIZE,
          threshold: thr,
          ...(ws ? { workspace_id: ws } : {}),
        });
        const res = await axios.get(`${API}/search?${params}`);
        setResults(res.data);
        setPage(targetPage);
      } catch {
        setError('Search failed. Please try again.');
      } finally {
        setLoading(false);
      }
    },
    [query, mode, threshold, workspaceId]
  );

  useEffect(() => {
    fetchPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e) => {
    e?.preventDefault();
    fetchPage(0);
  };

  const handleWsChange = (val) => {
    setWsId(val);
    setWsMenuOpen(false);
    fetchPage(0, { workspaceId: val });
  };

  const handleModeChange = (val) => {
    setMode(val);
    fetchPage(0, { mode: val });
  };

  // Group results by their match-reason label (client-side; the backend does not
  // provide semantic reason clusters yet).
  const groups = useMemo(() => {
    const map = new Map();
    for (const img of results) {
      const r = reasonFor(img);
      const label = r?.label ?? 'no match info';
      if (!map.has(label)) map.set(label, { label, score: r?.score ?? null, items: [] });
      const g = map.get(label);
      g.items.push(img);
      if (r?.score != null) g.score = Math.max(g.score ?? 0, r.score);
    }
    return [...map.values()].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  }, [results]);

  const hasPrev = page > 0;
  const hasNext = results.length === PAGE_SIZE;
  const semanticActive = mode === 'semantic' || mode === 'hybrid';
  const activeWs = workspaces.find((w) => w._id === workspaceId);
  const openImage = (id) => navigate(`/image/${id}`);

  const grid = (items) => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 13 }}>
      {items.map((img) => (
        <ResultCell key={img._id} img={img} onOpen={() => openImage(img._id)} />
      ))}
    </div>
  );

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', color: AP.ink, overflow: 'hidden' }}>
      {/* ── Top app bar: query (⌘K, active glow) · search ── */}
      <form
        onSubmit={handleSearch}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '16px 20px',
          borderBottom: `1px solid ${AP.line}`,
          background: AP.panel,
          flex: '0 0 auto',
        }}
      >
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '10px 13px',
            borderRadius: 12,
            background: AP.card,
            border: `1px solid ${focused ? AP.lumenLine : AP.line2}`,
            boxShadow: focused ? `0 0 0 3px ${AP.lumenBg}, 0 0 26px rgba(124,108,247,.22)` : 'none',
            transition: 'all .16s',
          }}
        >
          <MagIcon size={17} c={focused ? AP.lumenSoft : AP.ink3} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Search your library — describe a scene, object, or filename…"
            style={{
              flex: 1,
              minWidth: 0,
              fontSize: 15,
              fontFamily: AP.sans,
              color: AP.ink,
              background: 'transparent',
              border: 'none',
              outline: 'none',
            }}
          />
          <Kbd>⌘K</Kbd>
        </div>
        <LumenBtn type="submit" disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </LumenBtn>
      </form>

      {/* ── Body: left rail + results ── */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* left rail */}
        <div
          className="ap-scroll"
          style={{
            width: 234,
            flex: '0 0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 22,
            padding: '20px 18px',
            borderRight: `1px solid ${AP.line}`,
            overflowY: 'auto',
          }}
        >
          {/* workspace selector (Ember) */}
          <div style={{ position: 'relative' }}>
            <Eyebrow style={{ display: 'block', marginBottom: 9 }}>Workspace</Eyebrow>
            <button
              type="button"
              onClick={() => setWsMenuOpen((v) => !v)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                padding: '11px 12px',
                borderRadius: 11,
                cursor: 'pointer',
                background: AP.card,
                border: `1px solid ${AP.line2}`,
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
                <Dot c={AP.ember} size={8} glow />
                <span
                  style={{
                    fontFamily: AP.sans,
                    fontSize: 14,
                    fontWeight: 600,
                    color: AP.ink,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {activeWs?.name ?? 'All workspaces'}
                </span>
              </span>
              <span style={{ fontSize: 11, color: AP.ink3 }}>▾</span>
            </button>
            {wsMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: 6,
                  background: AP.card,
                  border: `1px solid ${AP.line2}`,
                  borderRadius: 11,
                  padding: 6,
                  zIndex: 30,
                  boxShadow: '0 12px 30px rgba(0,0,0,.5)',
                  maxHeight: 260,
                  overflowY: 'auto',
                }}
              >
                {[{ _id: '', name: 'All workspaces' }, ...workspaces].map((ws) => (
                  <button
                    key={ws._id || 'all'}
                    type="button"
                    onClick={() => handleWsChange(ws._id)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 10px',
                      borderRadius: 8,
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontFamily: AP.sans,
                      fontSize: 13,
                      fontWeight: ws._id === workspaceId ? 600 : 500,
                      color: ws._id === workspaceId ? AP.ink : AP.ink2,
                      background: ws._id === workspaceId ? 'rgba(255,255,255,0.06)' : 'transparent',
                      border: 'none',
                    }}
                  >
                    <Dot c={ws._id === workspaceId ? AP.ember : AP.ink4} size={6} />
                    {ws.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* filters */}
          <div>
            <Eyebrow style={{ display: 'block', marginBottom: 11 }}>Search mode</Eyebrow>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {MODES.map((m) => {
                const on = mode === m.value;
                return (
                  <button
                    key={m.value}
                    type="button"
                    title={m.desc}
                    onClick={() => handleModeChange(m.value)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 11px',
                      borderRadius: 9,
                      cursor: 'pointer',
                      fontFamily: AP.sans,
                      fontSize: 13,
                      fontWeight: on ? 600 : 500,
                      color: on ? AP.lumenSoft : AP.ink2,
                      background: on ? AP.lumenBg : 'rgba(255,255,255,0.02)',
                      border: `1px solid ${on ? AP.lumenLine : AP.line}`,
                      transition: 'all .14s',
                    }}
                  >
                    {m.label}
                    {on && <span style={{ fontSize: 11, color: AP.lumen }}>✦</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* similarity threshold */}
          <div style={{ opacity: semanticActive ? 1 : 0.4, pointerEvents: semanticActive ? 'auto' : 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 9 }}>
              <Eyebrow>Min similarity</Eyebrow>
              <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.lumenSoft }}>
                {(threshold * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              onMouseUp={() => fetchPage(0)}
              style={{ width: '100%', accentColor: AP.lumen, cursor: 'pointer' }}
            />
          </div>

          {/* applied facets */}
          <div>
            <Eyebrow style={{ display: 'block', marginBottom: 10 }}>Applied</Eyebrow>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              <FacetPill primary>{mode}</FacetPill>
              {activeWs && <FacetPill onRemove={() => handleWsChange('')}>{activeWs.name}</FacetPill>}
              {semanticActive && threshold > 0 && (
                <FacetPill
                  onRemove={() => {
                    setThreshold(0);
                    fetchPage(0, { threshold: 0 });
                  }}
                >
                  ≥{(threshold * 100).toFixed(0)}%
                </FacetPill>
              )}
            </div>
          </div>

          <div
            style={{
              marginTop: 'auto',
              display: 'flex',
              gap: 7,
              alignItems: 'flex-start',
              paddingTop: 14,
              color: AP.ink3,
            }}
          >
            <span style={{ color: AP.lumen, fontSize: 12 }}>✦</span>
            <span style={{ fontFamily: AP.sans, fontSize: 12, lineHeight: 1.4 }}>
              Facets scope the same query — they don't re-search.
            </span>
          </div>
        </div>

        {/* results */}
        <div
          className="ap-scroll"
          style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
            padding: 20,
            overflowY: 'auto',
          }}
        >
          {/* results header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 9 }}>
              <span style={{ fontSize: 15, fontWeight: 600, color: AP.ink }}>
                {results.length}
                {hasNext ? '+' : ''}
              </span>
              <span style={{ fontFamily: AP.mono, fontSize: 11.5, color: AP.ink3 }}>
                results{grouped ? ` · ${groups.length} groups` : ''} · page {page + 1}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <SelectControl label="Sort" value="match" title="Results are ranked by match score" />
              <SelectControl
                label="Group"
                value="reason"
                accent
                active={grouped}
                onClick={() => setGrouped((g) => !g)}
              />
            </div>
          </div>

          {error && (
            <div
              style={{
                padding: '12px 15px',
                borderRadius: 11,
                background: 'rgba(240,86,107,.1)',
                border: '1px solid rgba(240,86,107,.35)',
                fontFamily: AP.sans,
                fontSize: 13,
                color: '#f0566b',
                display: 'flex',
                justifyContent: 'space-between',
                gap: 10,
              }}
            >
              {error}
              <button
                type="button"
                onClick={() => setError('')}
                style={{ background: 'transparent', border: 'none', color: '#f0566b', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>
          )}

          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '90px 0' }}>
              <span
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 99,
                  border: `2px solid ${AP.lumenBg2}`,
                  borderTopColor: AP.lumen,
                  animation: 'spin 0.8s linear infinite',
                }}
              />
              <style>{'@keyframes spin{to{transform:rotate(360deg)}}'}</style>
            </div>
          ) : results.length > 0 ? (
            grouped ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {groups.map((g, gi) => {
                  const isCol = !!collapsed[gi];
                  return (
                    <div key={g.label} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <GroupHeader
                        label={g.label}
                        score={g.score}
                        count={g.items.length}
                        collapsed={isCol}
                        onToggle={() => setCollapsed((c) => ({ ...c, [gi]: !c[gi] }))}
                      />
                      {!isCol && grid(g.items)}
                    </div>
                  );
                })}
              </div>
            ) : (
              grid(results)
            )
          ) : !error ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 12,
                padding: '90px 0',
                textAlign: 'center',
              }}
            >
              <MagIcon size={30} c={AP.ink4} />
              <div>
                <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 14, fontWeight: 600, color: AP.ink2 }}>
                  {query ? `No results for “${query}”` : 'No images found'}
                </p>
                <p style={{ margin: '5px 0 0', fontFamily: AP.sans, fontSize: 12, color: AP.ink3 }}>
                  {query
                    ? 'Try a different query or switch to Hybrid mode'
                    : 'Add images to a workspace and wait for them to be processed'}
                </p>
              </div>
            </div>
          ) : null}

          {/* pagination */}
          {!loading && results.length > 0 && (hasPrev || hasNext) && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, paddingTop: 8 }}>
              <GhostBtn onClick={() => fetchPage(page - 1)} disabled={!hasPrev}>
                ‹ Previous
              </GhostBtn>
              <span style={{ fontFamily: AP.mono, fontSize: 12, color: AP.ink3 }}>page {page + 1}</span>
              <GhostBtn onClick={() => fetchPage(page + 1)} disabled={!hasNext}>
                Next ›
              </GhostBtn>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ImageQueryView;
