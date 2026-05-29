import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';

const API = 'http://localhost:8000';

const EXTENSION_OPTIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.heic', '.avif'];

/* ── Shared styles ──────────────────────────────────────────────── */
const fieldLabel = 'text-[11px] font-semibold text-slate-500 uppercase tracking-wider';
const fieldInput =
  'bg-slate-800/60 border border-slate-700/60 focus:border-violet-500/60 ' +
  'focus:ring-2 focus:ring-violet-500/10 rounded-xl px-3.5 py-2.5 text-sm ' +
  'text-slate-200 placeholder-slate-500 outline-none transition-all w-full';

/* ── Status Badge ───────────────────────────────────────────────── */
function StatusBadge({ active }) {
  return active ? (
    <span className="flex items-center gap-1.5 text-xs font-semibold text-green-400
                     bg-green-900/30 border border-green-700/40 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
      Active
    </span>
  ) : (
    <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500
                     bg-slate-800/50 border border-slate-700/40 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-slate-600" />
      Paused
    </span>
  );
}

/* ── Server-side Directory Browser ─────────────────────────────── */
function DirectoryPathInput({ value, onChange }) {
  const [open, setOpen]         = useState(false);
  const [browsePath, setBrowsePath] = useState('');
  const [entries, setEntries]   = useState([]);
  const [parent, setParent]     = useState(null);
  const [loading, setLoading]   = useState(false);
  const [browseError, setBrowseError] = useState('');

  const fetchDir = useCallback(async (path) => {
    setLoading(true);
    setBrowseError('');
    try {
      const params = path ? `?path=${encodeURIComponent(path)}` : '';
      const res = await axios.get(`${API}/workspaces/browse${params}`);
      setBrowsePath(res.data.current);
      setParent(res.data.parent);
      setEntries(res.data.entries);
    } catch (err) {
      setBrowseError(err.response?.data?.detail ?? 'Failed to list directory');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleOpen = () => {
    setOpen(true);
    // Start from the currently typed path if valid, otherwise empty (→ roots)
    fetchDir(value.trim() || '');
  };

  const handleNavigate = (path) => fetchDir(path);

  const handleSelect = (path) => {
    onChange(path);
    setOpen(false);
  };

  return (
    <div className="flex flex-col gap-2">
      {/* Text input + Browse button */}
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="/home/user/Photos  or  C:\Users\user\Photos"
          className={`${fieldInput} font-mono flex-1`}
        />
        <button
          type="button"
          onClick={handleOpen}
          title="Browse server-side filesystem"
          className="shrink-0 flex items-center gap-1.5 px-3 py-2.5 rounded-xl
                     bg-slate-800/60 border border-slate-700/60 text-slate-400
                     hover:text-slate-200 hover:border-slate-600 transition-all text-sm font-semibold"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          Browse
        </button>
      </div>

      <p className="text-[11px] text-slate-600 leading-snug">
        Path must exist on the machine running the PixQuery backend.
      </p>

      {/* Browser modal — rendered via portal so it escapes any transformed ancestor */}
      {open && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {/* Backdrop */}
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)' }}
               onClick={() => setOpen(false)} />

          {/* Dialog */}
          <div style={{
            position: 'relative',
            width: '100%',
            maxWidth: '560px',
            height: '72vh',
            maxHeight: '580px',
            minHeight: '300px',
            display: 'flex',
            flexDirection: 'column',
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '16px',
            boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
            overflow: 'hidden',
            margin: '0 16px',
          }}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
              <span style={{ fontWeight: 700, color: '#e2e8f0', fontSize: '14px' }}>Browse Server Filesystem</span>
              <button onClick={() => setOpen(false)}
                      style={{ color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Breadcrumb / current path */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', background: '#1e293b55', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
              {parent !== null && (
                <button
                  onClick={() => handleNavigate(parent)}
                  style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#a78bfa', background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, flexShrink: 0, padding: 0 }}
                >
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  Up
                </button>
              )}
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}
                    title={browsePath}>
                {browsePath || 'Filesystem roots'}
              </span>
              {loading && (
                <span style={{ width: 12, height: 12, border: '2px solid #4c1d95', borderTopColor: '#a78bfa', borderRadius: '50%', animation: 'spin 0.7s linear infinite', flexShrink: 0 }} />
              )}
            </div>

            {/* Error */}
            {browseError && (
              <div style={{ padding: '8px 16px', background: '#450a0a55', borderBottom: '1px solid #7f1d1d', color: '#f87171', fontSize: 12, flexShrink: 0 }}>
                {browseError}
              </div>
            )}

            {/* Directory listing — this is the scrollable region */}
            <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', scrollbarWidth: 'thin', scrollbarColor: '#4c1d95 transparent' }}>
              {entries.length === 0 && !loading && (
                <p style={{ textAlign: 'center', color: '#475569', fontSize: 14, padding: '32px 0' }}>Empty directory</p>
              )}
              {entries.map(entry => (
                <div
                  key={entry.path}
                  onClick={() => entry.is_dir && handleNavigate(entry.path)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 16px',
                    borderBottom: '1px solid #1e293b80',
                    cursor: entry.is_dir ? 'pointer' : 'default',
                    opacity: entry.is_dir ? 1 : 0.35,
                    userSelect: 'none',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={e => { if (entry.is_dir) e.currentTarget.style.background = '#1e293b99'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <svg width="16" height="16" style={{ color: entry.is_dir ? '#a78bfa' : '#475569', flexShrink: 0 }}
                       fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    {entry.is_dir
                      ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0121 9.414V19a2 2 0 01-2 2z" />
                    }
                  </svg>
                  <span style={{ flex: 1, fontSize: 13, color: '#cbd5e1', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {entry.name}
                  </span>
                  {entry.is_dir && (
                    <button
                      onClick={e => { e.stopPropagation(); handleSelect(entry.path); }}
                      style={{ flexShrink: 0, fontSize: 10, fontWeight: 700, color: '#a78bfa', background: 'rgba(109,40,217,0.25)', border: '1px solid rgba(109,40,217,0.4)', padding: '2px 8px', borderRadius: 999, cursor: 'pointer' }}
                    >
                      Select
                    </button>
                  )}
                </div>
              ))}
            </div>

            {/* Footer — use current dir */}
            {browsePath && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '12px 16px', borderTop: '1px solid #1e293b', flexShrink: 0 }}>
                <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                  {browsePath}
                </span>
                <button
                  onClick={() => handleSelect(browsePath)}
                  style={{ flexShrink: 0, padding: '8px 16px', borderRadius: 12, background: '#7c3aed', color: '#fff', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}
                >
                  Use This Folder
                </button>
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

/* ── Pipeline Selector ──────────────────────────────────────────── */
function PipelineSelector({ pipelines, selectedIds, onToggle }) {
  if (pipelines.length === 0) {
    return (
      <div className="flex items-center gap-3 px-4 py-4 bg-slate-800/20 border border-dashed
                      border-slate-700/60 rounded-xl">
        <svg className="w-5 h-5 text-slate-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
        <div>
          <p className="text-sm text-slate-500">No pipelines defined yet</p>
          <p className="text-[11px] text-slate-600 mt-0.5">
            Go to <span className="text-violet-400 font-semibold">Pipeline Manager</span> to create one first
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {pipelines.map(p => {
        const selected = selectedIds.includes(p._id);
        const nodeCount = (p.nodes ?? []).length;
        return (
          <button
            key={p._id}
            type="button"
            onClick={() => onToggle(p._id)}
            className={`flex items-center gap-3 px-3.5 py-3 rounded-xl border text-left
                        transition-all duration-150 ${
              selected
                ? 'bg-violet-900/25 border-violet-500/50 shadow-[inset_0_0_0_1px_rgba(139,92,246,0.1)]'
                : 'bg-slate-800/30 border-slate-700/50 hover:border-slate-600 hover:bg-slate-800/50'
            }`}
          >
            {/* Checkbox */}
            <div className={`w-4 h-4 rounded flex-shrink-0 flex items-center justify-center
                             border transition-all ${
              selected ? 'bg-violet-600 border-violet-500' : 'border-slate-600 bg-transparent'
            }`}>
              {selected && (
                <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-semibold truncate ${selected ? 'text-violet-200' : 'text-slate-300'}`}>
                {p.name}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {nodeCount === 0
                  ? 'No nodes — empty pipeline'
                  : `${nodeCount} node${nodeCount !== 1 ? 's' : ''}`}
              </p>
            </div>

            {/* Selected indicator */}
            {selected && (
              <span className="shrink-0 text-[10px] font-bold text-violet-400 bg-violet-900/40
                               border border-violet-700/40 px-2 py-0.5 rounded-full">
                selected
              </span>
            )}
          </button>
        );
      })}

      {selectedIds.length === 0 && (
        <p className="text-[11px] text-amber-500/80 flex items-center gap-1.5 px-1">
          <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          No pipeline selected — files will be ingested but not processed
        </p>
      )}
    </div>
  );
}

/* ── Create / Edit Drawer ───────────────────────────────────────── */
function WorkspaceDrawer({ workspace, pipelines, onSave, onClose }) {
  const isEdit = Boolean(workspace?._id);
  const [form, setForm] = useState({
    name:           workspace?.name ?? '',
    workspace_path: workspace?.workspace_path ?? '',
    pipeline_ids:   workspace?.pipeline_ids ?? [],
    extensions:     workspace?.extensions ?? ['.jpg', '.jpeg', '.png', '.webp'],
    active:         workspace?.active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const toggleExt = (ext) =>
    setForm(f => ({
      ...f,
      extensions: f.extensions.includes(ext)
        ? f.extensions.filter(e => e !== ext)
        : [...f.extensions, ext],
    }));

  const togglePipeline = (id) =>
    setForm(f => ({
      ...f,
      pipeline_ids: f.pipeline_ids.includes(id)
        ? f.pipeline_ids.filter(p => p !== id)
        : [...f.pipeline_ids, id],
    }));

  const handleSave = async () => {
    if (!form.name.trim())           { setError('Name is required'); return; }
    if (!form.workspace_path.trim()) { setError('Directory path is required'); return; }
    setSaving(true);
    setError('');
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[480px] bg-slate-900
                      border-l border-slate-800 flex flex-col shadow-2xl">

        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div>
            <h2 className="font-bold text-slate-100 text-base">
              {isEdit ? 'Edit Workspace' : 'New Workspace'}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure a watched folder and its processing pipelines
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-500
                       hover:text-slate-300 hover:bg-slate-800 transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-y-auto px-5 py-5 flex flex-col gap-6"
             style={{ scrollbarWidth: 'thin', scrollbarColor: '#4c1d95 transparent' }}>

          {/* Name */}
          <div className="flex flex-col gap-1.5">
            <label className={fieldLabel}>Workspace Name</label>
            <input
              autoFocus
              type="text"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="My Photos"
              className={fieldInput}
            />
          </div>

          {/* Directory path */}
          <div className="flex flex-col gap-1.5">
            <label className={fieldLabel}>Directory Path</label>
            <DirectoryPathInput
              value={form.workspace_path}
              onChange={v => setForm(f => ({ ...f, workspace_path: v }))}
            />
          </div>

          {/* Divider */}
          <div className="border-t border-slate-800" />

          {/* File Extensions */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className={fieldLabel}>File Extensions</label>
              <span className="text-[11px] text-slate-600">
                {form.extensions.length} selected
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {EXTENSION_OPTIONS.map(ext => (
                <button
                  key={ext}
                  type="button"
                  onClick={() => toggleExt(ext)}
                  className={`px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border transition-all ${
                    form.extensions.includes(ext)
                      ? 'bg-violet-600/20 border-violet-500/50 text-violet-300'
                      : 'bg-slate-800/40 border-slate-700/50 text-slate-500 hover:text-slate-300 hover:border-slate-600'
                  }`}
                >
                  {ext}
                </button>
              ))}
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-slate-800" />

          {/* Pipelines */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className={fieldLabel}>Processing Pipelines</label>
              {form.pipeline_ids.length > 0 && (
                <span className="text-[11px] text-violet-400 font-semibold">
                  {form.pipeline_ids.length} selected
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-600 -mt-0.5">
              New files in this folder will be processed by all selected pipelines in parallel.
            </p>
            <PipelineSelector
              pipelines={pipelines}
              selectedIds={form.pipeline_ids}
              onToggle={togglePipeline}
            />
          </div>

          {/* Divider */}
          <div className="border-t border-slate-800" />

          {/* Active toggle */}
          <div className="flex items-center justify-between px-3.5 py-3.5
                          bg-slate-800/30 rounded-xl border border-slate-700/50">
            <div>
              <p className="text-sm font-semibold text-slate-300">Active Monitoring</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Watch for new files and trigger pipelines automatically
              </p>
            </div>
            <button
              type="button"
              onClick={() => setForm(f => ({ ...f, active: !f.active }))}
              className={`relative shrink-0 w-10 h-5 rounded-full transition-colors duration-200
                          ${form.active ? 'bg-violet-600' : 'bg-slate-700'}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm
                                transition-all duration-200
                                ${form.active ? 'left-[22px]' : 'left-0.5'}`} />
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="px-5 py-3 bg-red-950/40 border-t border-red-800/50
                          text-sm text-red-400 shrink-0 flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {error}
          </div>
        )}

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-800 flex gap-3 shrink-0">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-700 text-sm font-semibold
                       text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-blue-600
                       hover:from-violet-500 hover:to-blue-500 text-white text-sm font-semibold
                       disabled:opacity-50 transition-all shadow-[0_0_16px_rgba(139,92,246,0.2)]"
          >
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Workspace'}
          </button>
        </div>
      </div>
    </>
  );
}

/* ── Workspace Card ─────────────────────────────────────────────── */
function WorkspaceCard({ workspace, pipelines, onEdit, onDelete, onScan, scanning }) {
  const linkedPipelines = pipelines.filter(p => workspace.pipeline_ids?.includes(p._id));

  return (
    <div
      className={`flex flex-col gap-3 p-5 bg-slate-900/60 border rounded-2xl backdrop-blur transition-all ${
        workspace.active
          ? 'border-slate-700/60 hover:border-violet-500/30 hover:shadow-[0_0_20px_rgba(139,92,246,0.08)]'
          : 'border-slate-800/40 opacity-60'
      }`}
      style={workspace.active ? { borderTopColor: 'rgba(139,92,246,0.45)', borderTopWidth: 2 } : {}}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-slate-200">{workspace.name}</h3>
            <StatusBadge active={workspace.active} />
          </div>
          <p className="text-[11px] text-slate-500 font-mono mt-1 truncate" title={workspace.workspace_path}>
            {workspace.workspace_path}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => onEdit(workspace)}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500
                       hover:text-violet-400 hover:bg-slate-800 transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5
                       m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            onClick={() => onDelete(workspace._id)}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500
                       hover:text-red-400 hover:bg-slate-800 transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7
                       m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Pipelines row */}
      <div>
        <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
          Pipelines
        </p>
        <div className="flex flex-wrap gap-1.5">
          {linkedPipelines.length > 0 ? (
            linkedPipelines.map(p => (
              <span
                key={p._id}
                className="text-[11px] font-semibold text-violet-300 bg-violet-900/30
                           border border-violet-700/40 px-2.5 py-1 rounded-full"
              >
                {p.name}
              </span>
            ))
          ) : (
            <span className="text-[11px] text-slate-600 italic">No pipelines assigned</span>
          )}
        </div>
      </div>

      {/* Extensions row */}
      <div>
        <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
          File Types
        </p>
        <div className="flex flex-wrap gap-1">
          {(workspace.extensions ?? []).map(ext => (
            <span
              key={ext}
              className="text-[10px] text-slate-500 bg-slate-800/50 px-2 py-0.5 rounded
                         font-mono border border-slate-700/40"
            >
              {ext}
            </span>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 mt-1">
        <span className="text-[10px] text-slate-700">
          Added {workspace.created_at ? new Date(workspace.created_at).toLocaleDateString() : '—'}
        </span>
        <button
          onClick={() => onScan(workspace._id)}
          disabled={scanning || !workspace.active}
          title={!workspace.active ? 'Workspace is paused' : 'Trigger an immediate scan of this folder'}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800/60
                     border border-slate-700/50 text-xs font-semibold text-slate-400
                     hover:text-violet-300 hover:border-violet-500/40
                     disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {scanning ? (
            <span className="w-3 h-3 border border-slate-500 border-t-violet-400 rounded-full animate-spin" />
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9
                       m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          {scanning ? 'Scanning…' : 'Scan Now'}
        </button>
      </div>
    </div>
  );
}

/* ── Main View ──────────────────────────────────────────────────── */
function ImageUploadView() {
  const [workspaces, setWorkspaces] = useState([]);
  const [pipelines, setPipelines]   = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [drawer, setDrawer]         = useState(null); // null | 'new' | workspace object
  const [scanning, setScanning]     = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [wsRes, plRes] = await Promise.all([
        axios.get(`${API}/workspaces`),
        axios.get(`${API}/pipelines`),
      ]);
      setWorkspaces(wsRes.data);
      setPipelines(plRes.data);
    } catch {
      setError('Failed to load workspaces');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async (form) => {
    if (drawer?._id) {
      await axios.put(`${API}/workspaces/${drawer._id}`, form);
    } else {
      await axios.post(`${API}/workspaces`, form);
    }
    await loadData();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this workspace? This will not delete any images.')) return;
    try {
      await axios.delete(`${API}/workspaces/${id}`);
      await loadData();
    } catch {
      setError('Delete failed');
    }
  };

  const handleScan = async (id) => {
    setScanning(id);
    try {
      await axios.post(`${API}/workspaces/${id}/scan`);
    } catch {
      setError('Scan trigger failed');
    } finally {
      setScanning(null);
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-10">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Workspaces</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Watched folders — new images are automatically picked up and sent through your pipelines
          </p>
        </div>
        <button
          onClick={() => setDrawer('new')}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl
                     bg-gradient-to-r from-violet-600 to-blue-600
                     hover:from-violet-500 hover:to-blue-500
                     text-white text-sm font-semibold transition-all
                     shadow-[0_0_16px_rgba(139,92,246,0.25)]"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Workspace
        </button>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-xl px-4 py-3 text-sm text-red-400
                        flex items-center justify-between gap-3">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-700 hover:text-red-500 shrink-0">✕</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
        </div>
      ) : workspaces.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800
                          flex items-center justify-center">
            <svg className="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <div>
            <p className="font-semibold text-slate-300">No workspaces yet</p>
            <p className="text-sm text-slate-600 mt-1 max-w-xs">
              Create a workspace to start watching a folder — new images will be processed automatically
            </p>
          </div>
          <button
            onClick={() => setDrawer('new')}
            className="px-5 py-2.5 rounded-xl bg-violet-600/20 border border-violet-500/30
                       text-violet-300 text-sm font-semibold hover:bg-violet-600/30 transition-all"
          >
            Create your first workspace
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {workspaces.map(ws => (
            <WorkspaceCard
              key={ws._id}
              workspace={ws}
              pipelines={pipelines}
              onEdit={setDrawer}
              onDelete={handleDelete}
              onScan={handleScan}
              scanning={scanning === ws._id}
            />
          ))}
        </div>
      )}

      {drawer !== null && (
        <WorkspaceDrawer
          workspace={drawer === 'new' ? null : drawer}
          pipelines={pipelines}
          onSave={handleSave}
          onClose={() => setDrawer(null)}
        />
      )}
    </div>
  );
}

export default ImageUploadView;
