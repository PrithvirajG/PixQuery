import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

const API       = 'http://localhost:8000';
const PAGE_SIZE = 24;

const MODES = [
  { value: 'keyword',  label: 'Keyword',  desc: 'Match on file paths & captions' },
  { value: 'semantic', label: 'Semantic', desc: 'Vector search via CLIP embeddings' },
  { value: 'hybrid',   label: 'Hybrid',   desc: 'Keyword + semantic, re-ranked' },
];

/* ── Image Card ─────────────────────────────────────────────────── */
function ImageCard({ img }) {
  const filename = img.current_path?.split(/[\\/]/).pop() ?? 'Image';
  return (
    <Link
      to={`/image/${img._id}`}
      className="group flex flex-col bg-slate-900/60 border border-slate-800 rounded-2xl
                 overflow-hidden hover:border-violet-500/40
                 hover:shadow-[0_0_24px_rgba(139,92,246,0.15)]
                 transition-all duration-300 backdrop-blur"
    >
      <div className="aspect-square bg-slate-800/50 flex items-center justify-center overflow-hidden">
        <img
          src={`${API}/images/${img._id}/thumbnail`}
          alt={filename}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          onError={e => { e.target.style.display = 'none'; }}
        />
      </div>
      <div className="p-3 flex flex-col gap-1.5">
        <p className="text-xs font-semibold text-slate-200 truncate" title={filename}>{filename}</p>
        {img.description && (
          <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">{img.description}</p>
        )}
        <div className="flex items-center justify-between mt-0.5">
          <span className="text-[10px] text-slate-600">
            {img.size_bytes ? `${(img.size_bytes / 1024).toFixed(1)} KB` : ''}
          </span>
          {img.score !== undefined && img.score < 1.0 && (
            <span className="text-[10px] font-bold text-violet-400 bg-violet-900/30
                             px-2 py-0.5 rounded-full border border-violet-800/40">
              {(img.score * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

/* ── Main View ──────────────────────────────────────────────────── */
function ImageQueryView() {
  const [query, setQuery]           = useState('');
  const [results, setResults]       = useState([]);
  const [total, setTotal]           = useState(0);      // total matched (approx)
  const [page, setPage]             = useState(0);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');
  const [mode, setMode]             = useState('keyword');
  const [threshold, setThreshold]   = useState(0.0);
  const [workspaceId, setWsId]      = useState('');
  const [workspaces, setWorkspaces] = useState([]);
  const inputRef = useRef(null);

  /* Load workspaces once */
  useEffect(() => {
    axios.get(`${API}/workspaces`).then(r => setWorkspaces(r.data)).catch(() => {});
    inputRef.current?.focus();
  }, []);

  /* Core fetch — called by search form submit AND pagination */
  const fetchPage = useCallback(async (targetPage, opts = {}) => {
    const q         = opts.query         ?? query;
    const m         = opts.mode          ?? mode;
    const thr       = opts.threshold     ?? threshold;
    const ws        = opts.workspaceId   ?? workspaceId;

    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        query:    q.trim(),
        mode:     m,
        top_k:    PAGE_SIZE,
        skip:     targetPage * PAGE_SIZE,
        threshold: thr,
        ...(ws ? { workspace_id: ws } : {}),
      });
      const res = await axios.get(`${API}/search?${params}`);
      const data = res.data;
      setResults(data);
      // If we got a full page, assume there's more; otherwise we know we're at the end
      setTotal(prev =>
        data.length < PAGE_SIZE
          ? targetPage * PAGE_SIZE + data.length   // exact total known
          : Math.max(prev, (targetPage + 1) * PAGE_SIZE + 1) // at least one more page
      );
      setPage(targetPage);
    } catch {
      setError('Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [query, mode, threshold, workspaceId]);

  /* Auto-load all images on mount */
  useEffect(() => {
    fetchPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e) => {
    e?.preventDefault();
    setTotal(0);
    fetchPage(0);
  };

  /* Re-fetch immediately when workspace or mode filter changes */
  const handleWsChange = (val) => {
    setWsId(val);
    setTotal(0);
    setPage(0);
    fetchPage(0, { workspaceId: val });
  };

  const handleModeChange = (val) => {
    setMode(val);
    setTotal(0);
    setPage(0);
    fetchPage(0, { mode: val });
  };

  const hasPrev = page > 0;
  const hasNext = results.length === PAGE_SIZE;

  const semanticActive = mode === 'semantic' || mode === 'hybrid';

  return (
    <div className="flex flex-col gap-6 pb-10">

      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100">Search Images</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Browse your library or search by keyword, semantic meaning, or a combination of both
        </p>
      </div>

      {/* ── Search + Filters ─────────────────────────────────────── */}
      <form onSubmit={handleSearch} className="flex flex-col gap-4">

        {/* Row 1 — search input + button */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <div className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center">
              <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Type to search, or leave blank to browse all images…"
              className="w-full bg-slate-900/70 border border-slate-700/60
                         focus:border-violet-500/70 focus:shadow-[0_0_0_3px_rgba(139,92,246,0.12)]
                         rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-100
                         placeholder-slate-500 outline-none transition-all backdrop-blur"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="shrink-0 h-[42px] px-5 bg-gradient-to-r from-violet-600 to-blue-600
                       hover:from-violet-500 hover:to-blue-500 text-white text-sm font-semibold
                       rounded-xl disabled:opacity-50 transition-all
                       shadow-[0_0_16px_rgba(139,92,246,0.25)] flex items-center gap-2"
          >
            {loading ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Searching
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Search
              </>
            )}
          </button>
        </div>

        {/* Row 2 — always-visible filters */}
        <div className="bg-slate-900/50 border border-slate-800/70 rounded-2xl p-4
                        backdrop-blur flex flex-col gap-4">

          {/* Mode tabs */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Search Mode</span>
            <div className="flex gap-2">
              {MODES.map(m => (
                <button
                  key={m.value}
                  type="button"
                  title={m.desc}
                  onClick={() => handleModeChange(m.value)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    mode === m.value
                      ? 'bg-violet-600/20 border-violet-500/50 text-violet-300'
                      : 'bg-slate-800/40 border-slate-700/50 text-slate-400 hover:text-slate-200 hover:border-slate-600'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Second row: Workspace | Threshold */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {/* Workspace filter */}
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Workspace</span>
              <select
                value={workspaceId}
                onChange={e => handleWsChange(e.target.value)}
                className="bg-slate-800/60 border border-slate-700/60 focus:border-violet-500/60
                           rounded-xl px-3 py-2 text-sm text-slate-200 outline-none
                           transition-all w-full"
              >
                <option value="">All Workspaces</option>
                {workspaces.map(ws => (
                  <option key={ws._id} value={ws._id}>{ws.name}</option>
                ))}
              </select>
            </div>

            {/* Similarity threshold — only relevant for semantic/hybrid */}
            <div className={`flex flex-col gap-1.5 ${!semanticActive ? 'opacity-40 pointer-events-none' : ''}`}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  Min Similarity {!semanticActive && <span className="normal-case">(semantic only)</span>}
                </span>
                <span className="text-xs font-bold text-violet-400 tabular-nums">
                  {(threshold * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min={0} max={1} step={0.01}
                value={threshold}
                onChange={e => setThreshold(parseFloat(e.target.value))}
                className="w-full h-1.5 accent-violet-500 cursor-pointer mt-1"
              />
            </div>
          </div>
        </div>
      </form>

      {/* ── Error ───────────────────────────────────────────────── */}
      {error && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-xl px-4 py-3
                        text-sm text-red-400 flex items-center justify-between gap-3">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-700 hover:text-red-500 shrink-0">✕</button>
        </div>
      )}

      {/* ── Results header ──────────────────────────────────────── */}
      {!loading && (results.length > 0 || page > 0) && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">
            {query ? (
              <>
                Showing{' '}
                <span className="text-slate-300 font-semibold">{page * PAGE_SIZE + 1}–{page * PAGE_SIZE + results.length}</span>
                {' '}for{' '}
                <span className="text-slate-300 font-semibold">"{query}"</span>
                <span className="mx-1.5 text-slate-700">·</span>
                <span className="text-slate-600">{mode}</span>
              </>
            ) : (
              <>
                <span className="text-slate-300 font-semibold">{page * PAGE_SIZE + 1}–{page * PAGE_SIZE + results.length}</span>
                {' '}of your images
                {workspaceId && workspaces.find(w => w._id === workspaceId) && (
                  <> in <span className="text-violet-400 font-semibold">
                    {workspaces.find(w => w._id === workspaceId).name}
                  </span></>
                )}
              </>
            )}
          </p>
          {/* Pagination controls — top */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchPage(page - 1)}
              disabled={!hasPrev || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold
                         border border-slate-700 text-slate-400 hover:text-slate-200
                         hover:border-slate-600 disabled:opacity-30 disabled:cursor-not-allowed
                         transition-all"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Prev
            </button>
            <span className="text-xs text-slate-600 tabular-nums px-1">p.{page + 1}</span>
            <button
              onClick={() => fetchPage(page + 1)}
              disabled={!hasNext || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold
                         border border-slate-700 text-slate-400 hover:text-slate-200
                         hover:border-slate-600 disabled:opacity-30 disabled:cursor-not-allowed
                         transition-all"
            >
              Next
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* ── Grid ────────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
        </div>
      ) : results.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {results.map(img => <ImageCard key={img._id} img={img} />)}
        </div>
      ) : !error ? (
        /* Empty state */
        <div className="flex flex-col items-center gap-4 py-24 text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-violet-900/60 to-blue-900/60
                          border border-violet-800/40 flex items-center justify-center
                          shadow-[0_0_30px_rgba(139,92,246,0.1)]">
            <svg className="w-8 h-8 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14
                       m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            {query ? (
              <>
                <p className="text-sm font-semibold text-slate-300">
                  No results for <span className="text-slate-100">"{query}"</span>
                </p>
                <p className="text-xs text-slate-600 mt-1">Try a different query or switch to Hybrid mode</p>
              </>
            ) : (
              <>
                <p className="text-sm font-semibold text-slate-300">No images found</p>
                <p className="text-xs text-slate-600 mt-1">
                  Add images to a workspace and wait for them to be processed
                </p>
              </>
            )}
          </div>
        </div>
      ) : null}

      {/* ── Pagination — bottom ──────────────────────────────────── */}
      {!loading && results.length > 0 && (hasPrev || hasNext) && (
        <div className="flex items-center justify-center gap-3 pt-4">
          <button
            onClick={() => fetchPage(page - 1)}
            disabled={!hasPrev}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold
                       border border-slate-700 text-slate-400 hover:text-slate-200
                       hover:border-slate-600 disabled:opacity-30 disabled:cursor-not-allowed
                       transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Previous
          </button>
          <span className="text-sm text-slate-500 tabular-nums">Page {page + 1}</span>
          <button
            onClick={() => fetchPage(page + 1)}
            disabled={!hasNext}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold
                       border border-slate-700 text-slate-400 hover:text-slate-200
                       hover:border-slate-600 disabled:opacity-30 disabled:cursor-not-allowed
                       transition-all"
          >
            Next
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

export default ImageQueryView;
