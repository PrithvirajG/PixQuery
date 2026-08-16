// WorkspacesView — Aperture hi-fi Workspaces (Control Room), cards variant.
// A workspace = an indexed image collection with pipelines attached.
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '../lib/apiError';
import {
  AP,
  STATUS,
  Dot,
  MagIcon,
  GhostBtn,
  LumenBtn,
  ActBtn,
  Toggle,
  Eyebrow,
  HealthPill,
  StatBlock,
  ControlHeader,
  ApInput,
  ApSelect,
} from '../aperture/kit';

const API = 'http://localhost:8000';

const EXTENSION_OPTIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.heic', '.avif'];

const ROLE_COLORS = {
  owner: { c: AP.ember, bg: AP.emberBg, line: AP.emberLine },
  editor: { c: AP.lumenSoft, bg: AP.lumenBg, line: AP.lumenLine },
  viewer: { c: AP.ink2, bg: 'rgba(255,255,255,.04)', line: AP.line2 },
};

function RoleBadge({ role }) {
  const s = ROLE_COLORS[role] ?? ROLE_COLORS.viewer;
  return (
    <span
      style={{
        fontFamily: AP.mono,
        fontSize: 9.5,
        fontWeight: 600,
        letterSpacing: '.07em',
        textTransform: 'uppercase',
        color: s.c,
        background: s.bg,
        border: `1px solid ${s.line}`,
        padding: '2px 8px',
        borderRadius: 99,
        flex: '0 0 auto',
      }}
    >
      {role}
    </span>
  );
}

/* ── modal chrome ─────────────────────────────────────────────── */

function Modal({ onClose, width = 480, children, height }) {
  return createPortal(
    <div
      className="ap-screen"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        style={{ position: 'absolute', inset: 0, background: 'rgba(3,4,8,0.7)', backdropFilter: 'blur(4px)' }}
        onClick={onClose}
      />
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: width,
          maxHeight: '82vh',
          height,
          display: 'flex',
          flexDirection: 'column',
          background: AP.panel,
          border: `1px solid ${AP.line2}`,
          borderRadius: 16,
          boxShadow: '0 24px 60px rgba(0,0,0,.6)',
          overflow: 'hidden',
        }}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}

function ModalHeader({ title, sub, onClose }) {
  return (
    <div
      style={{
        padding: '15px 18px',
        borderBottom: `1px solid ${AP.line}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
        flex: '0 0 auto',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontFamily: AP.sans, fontSize: 15, fontWeight: 600, color: AP.ink }}>{title}</div>
        {sub && (
          <div
            style={{
              fontFamily: AP.mono,
              fontSize: 11,
              color: AP.ink3,
              marginTop: 2,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {sub}
          </div>
        )}
      </div>
      <button
        onClick={onClose}
        style={{
          width: 30,
          height: 30,
          borderRadius: 8,
          background: 'transparent',
          border: 'none',
          color: AP.ink3,
          fontSize: 15,
          cursor: 'pointer',
        }}
      >
        ✕
      </button>
    </div>
  );
}

function ErrorBanner({ children, onDismiss }) {
  if (!children) return null;
  return (
    <div
      style={{
        padding: '10px 14px',
        borderRadius: 10,
        background: STATUS.err.bg,
        border: `1px solid ${STATUS.err.line}`,
        fontFamily: AP.sans,
        fontSize: 12.5,
        color: STATUS.err.c,
        display: 'flex',
        justifyContent: 'space-between',
        gap: 10,
      }}
    >
      <span>{children}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          style={{ background: 'transparent', border: 'none', color: STATUS.err.c, cursor: 'pointer', flex: '0 0 auto' }}
        >
          ✕
        </button>
      )}
    </div>
  );
}

/* ── Server-side Directory Browser ────────────────────────────── */

function DirectoryPathInput({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [browsePath, setBrowsePath] = useState('');
  const [entries, setEntries] = useState([]);
  const [parent, setParent] = useState(null);
  const [loading, setLoading] = useState(false);
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
      setBrowseError(errorMessage(err, 'Failed to list directory'));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleOpen = () => {
    setOpen(true);
    fetchDir(value.trim() || '');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <ApInput
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="/home/user/Photos  or  C:\Users\user\Photos"
          style={{ fontFamily: AP.mono, fontSize: 12, flex: 1 }}
        />
        <GhostBtn onClick={handleOpen} title="Browse server-side filesystem">
          ▤ Browse
        </GhostBtn>
      </div>
      <span style={{ fontFamily: AP.sans, fontSize: 11, color: AP.ink4 }}>
        Path must exist on the machine running the PixQuery backend.
      </span>

      {open && (
        <Modal onClose={() => setOpen(false)} width={560} height="72vh">
          <ModalHeader title="Browse directories" sub={browsePath || 'filesystem roots'} onClose={() => setOpen(false)} />
          <div className="ap-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 10 }}>
            {browseError && (
              <div style={{ padding: 10 }}>
                <ErrorBanner>{browseError}</ErrorBanner>
              </div>
            )}
            {loading ? (
              <div style={{ padding: 20, fontFamily: AP.mono, fontSize: 12, color: AP.ink3 }}>loading…</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {parent !== null && (
                  <button
                    onClick={() => fetchDir(parent)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 9,
                      padding: '9px 12px',
                      borderRadius: 9,
                      cursor: 'pointer',
                      background: 'transparent',
                      border: 'none',
                      textAlign: 'left',
                      fontFamily: AP.mono,
                      fontSize: 12.5,
                      color: AP.ink2,
                    }}
                  >
                    ‹ ..
                  </button>
                )}
                {entries.map((e) => (
                  <div
                    key={e.path}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '7px 12px',
                      borderRadius: 9,
                    }}
                  >
                    <button
                      onClick={() => fetchDir(e.path)}
                      style={{
                        flex: 1,
                        minWidth: 0,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 9,
                        background: 'transparent',
                        border: 'none',
                        textAlign: 'left',
                        cursor: 'pointer',
                        fontFamily: AP.mono,
                        fontSize: 12.5,
                        color: AP.ink,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      <span style={{ color: AP.ember }}>▸</span> {e.name}
                    </button>
                    <ActBtn
                      onClick={() => {
                        onChange(e.path);
                        setOpen(false);
                      }}
                      accent
                    >
                      Select
                    </ActBtn>
                  </div>
                ))}
                {!entries.length && !browseError && (
                  <div style={{ padding: 16, fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3 }}>
                    No sub-directories here.
                  </div>
                )}
              </div>
            )}
          </div>
          <div style={{ padding: '12px 16px', borderTop: `1px solid ${AP.line}`, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <GhostBtn onClick={() => setOpen(false)}>Cancel</GhostBtn>
            {browsePath && (
              <LumenBtn
                onClick={() => {
                  onChange(browsePath);
                  setOpen(false);
                }}
              >
                Use this directory
              </LumenBtn>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

/* ── Create / Edit Drawer ─────────────────────────────────────── */

function WorkspaceDrawer({ workspace, pipelines, onSave, onClose }) {
  const isEdit = Boolean(workspace?._id);
  const [form, setForm] = useState({
    name: workspace?.name ?? '',
    workspace_path: workspace?.workspace_path ?? '',
    pipeline_ids: workspace?.pipeline_ids ?? [],
    extensions: workspace?.extensions ?? ['.jpg', '.jpeg', '.png', '.webp'],
    active: workspace?.active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const toggleExt = (ext) =>
    setForm((f) => ({
      ...f,
      extensions: f.extensions.includes(ext) ? f.extensions.filter((e) => e !== ext) : [...f.extensions, ext],
    }));

  const togglePipeline = (id) =>
    setForm((f) => ({
      ...f,
      pipeline_ids: f.pipeline_ids.includes(id) ? f.pipeline_ids.filter((p) => p !== id) : [...f.pipeline_ids, id],
    }));

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    if (!form.workspace_path.trim()) {
      setError('Directory path is required');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(errorMessage(err, 'Save failed'));
    } finally {
      setSaving(false);
    }
  };

  const label = { fontFamily: AP.mono, fontSize: 10.5, letterSpacing: '.09em', textTransform: 'uppercase', color: AP.ink3 };

  return createPortal(
    <div className="ap-screen" style={{ position: 'fixed', inset: 0, zIndex: 9000 }}>
      <div
        style={{ position: 'absolute', inset: 0, background: 'rgba(3,4,8,0.6)', backdropFilter: 'blur(3px)' }}
        onClick={onClose}
      />
      <div
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          bottom: 0,
          width: 480,
          maxWidth: '100%',
          background: AP.panel,
          borderLeft: `1px solid ${AP.line2}`,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '-24px 0 60px rgba(0,0,0,.5)',
        }}
      >
        <ModalHeader
          title={isEdit ? 'Edit workspace' : 'New workspace'}
          sub="a watched folder and its processing pipelines"
          onClose={onClose}
        />

        <div className="ap-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <span style={label}>Workspace name</span>
            <ApInput
              autoFocus
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="design-refs"
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <span style={label}>Directory path</span>
            <DirectoryPathInput value={form.workspace_path} onChange={(v) => setForm((f) => ({ ...f, workspace_path: v }))} />
          </div>

          <div style={{ height: 1, background: AP.line }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={label}>File extensions</span>
              <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink4 }}>{form.extensions.length} selected</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {EXTENSION_OPTIONS.map((ext) => {
                const on = form.extensions.includes(ext);
                return (
                  <button
                    key={ext}
                    type="button"
                    onClick={() => toggleExt(ext)}
                    style={{
                      fontFamily: AP.mono,
                      fontSize: 11,
                      fontWeight: 500,
                      padding: '5px 10px',
                      borderRadius: 8,
                      cursor: 'pointer',
                      color: on ? AP.lumenSoft : AP.ink3,
                      background: on ? AP.lumenBg : 'rgba(255,255,255,0.02)',
                      border: `1px solid ${on ? AP.lumenLine : AP.line}`,
                      transition: 'all .14s',
                    }}
                  >
                    {ext}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ height: 1, background: AP.line }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={label}>Processing pipelines</span>
              {form.pipeline_ids.length > 0 && (
                <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.lumenSoft }}>
                  {form.pipeline_ids.length} attached
                </span>
              )}
            </div>
            <span style={{ fontFamily: AP.sans, fontSize: 11.5, color: AP.ink4, lineHeight: 1.4 }}>
              New files in this folder will be processed by all attached pipelines in parallel.
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {pipelines.map((p) => {
                const on = form.pipeline_ids.includes(p._id);
                const nodeCount = (p.nodes ?? []).length;
                return (
                  <button
                    key={p._id}
                    type="button"
                    onClick={() => togglePipeline(p._id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 11,
                      padding: '11px 13px',
                      borderRadius: 11,
                      cursor: 'pointer',
                      textAlign: 'left',
                      background: on ? AP.lumenBg : 'rgba(255,255,255,0.02)',
                      border: `1px solid ${on ? AP.lumenLine : AP.line}`,
                      transition: 'all .14s',
                    }}
                  >
                    <span style={{ fontSize: 11, color: on ? AP.lumen : AP.ink4, flex: '0 0 auto' }}>◇</span>
                    <span style={{ flex: 1, minWidth: 0 }}>
                      <span
                        style={{
                          display: 'block',
                          fontFamily: AP.sans,
                          fontSize: 13.5,
                          fontWeight: 600,
                          color: on ? AP.ink : AP.ink2,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {p.name}
                      </span>
                      <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>
                        {nodeCount === 0 ? 'no nodes — empty pipeline' : `${nodeCount} node${nodeCount !== 1 ? 's' : ''}`}
                      </span>
                    </span>
                    {on && <Dot c={STATUS.ok.c} size={6} />}
                  </button>
                );
              })}
              {form.pipeline_ids.length === 0 && (
                <span style={{ fontFamily: AP.sans, fontSize: 11.5, color: AP.ember }}>
                  ⚠ No pipeline attached — files will be ingested but not processed.
                </span>
              )}
            </div>
          </div>

          <div style={{ height: 1, background: AP.line }} />

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              padding: '13px 14px',
              borderRadius: 12,
              background: AP.card,
              border: `1px solid ${AP.line2}`,
            }}
          >
            <div>
              <div style={{ fontFamily: AP.sans, fontSize: 13.5, fontWeight: 600, color: AP.ink }}>Active monitoring</div>
              <div style={{ fontFamily: AP.sans, fontSize: 11.5, color: AP.ink3, marginTop: 2 }}>
                Watch for new files and trigger pipelines automatically
              </div>
            </div>
            <Toggle on={form.active} onClick={() => setForm((f) => ({ ...f, active: !f.active }))} />
          </div>

          <ErrorBanner onDismiss={() => setError('')}>{error}</ErrorBanner>
        </div>

        <div style={{ padding: '14px 18px', borderTop: `1px solid ${AP.line}`, display: 'flex', gap: 10, flex: '0 0 auto' }}>
          <GhostBtn onClick={onClose} style={{ flex: 1, justifyContent: 'center' }}>
            Cancel
          </GhostBtn>
          <LumenBtn onClick={handleSave} disabled={saving} style={{ flex: 1, justifyContent: 'center' }}>
            {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Create workspace'}
          </LumenBtn>
        </div>
      </div>
    </div>,
    document.body
  );
}

/* ── Members Modal ────────────────────────────────────────────── */

function MembersModal({ workspace, onClose }) {
  const wid = workspace._id;
  const canManage = workspace.my_role === 'owner';

  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [newRole, setNewRole] = useState('viewer');
  const [busy, setBusy] = useState(false);

  const loadMembers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/workspaces/${wid}/members`);
      setMembers(res.data);
    } catch {
      setError('Failed to load members');
    } finally {
      setLoading(false);
    }
  }, [wid]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  // Debounced username prefix search for the invite autocomplete.
  useEffect(() => {
    if (!canManage) return undefined;
    const q = query.trim();
    if (!q) {
      setSuggestions([]);
      return undefined;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await axios.get(`${API}/workspaces/${wid}/user-search`, { params: { q } });
        setSuggestions(res.data);
      } catch {
        setSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, wid, canManage]);

  const addMember = async (username) => {
    setBusy(true);
    setError('');
    try {
      const res = await axios.post(`${API}/workspaces/${wid}/members`, { username, role: newRole });
      setMembers(res.data);
      setQuery('');
      setSuggestions([]);
    } catch (err) {
      setError(errorMessage(err, 'Failed to add member'));
    } finally {
      setBusy(false);
    }
  };

  const changeRole = async (userId, role) => {
    setError('');
    try {
      const res = await axios.patch(`${API}/workspaces/${wid}/members/${userId}`, { role });
      setMembers(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Failed to change role'));
    }
  };

  const removeMember = async (userId) => {
    setError('');
    try {
      const res = await axios.delete(`${API}/workspaces/${wid}/members/${userId}`);
      setMembers(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Failed to remove member'));
    }
  };

  return (
    <Modal onClose={onClose} width={440}>
      <ModalHeader title="Members" sub={workspace.name} onClose={onClose} />

      {canManage && (
        <div style={{ padding: '14px 18px', borderBottom: `1px solid ${AP.line}`, flex: '0 0 auto', position: 'relative' }}>
          <Eyebrow style={{ display: 'block', marginBottom: 8 }}>Invite by username</Eyebrow>
          <div style={{ display: 'flex', gap: 8 }}>
            <ApInput
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Start typing a username…"
              autoFocus
              style={{ flex: 1 }}
            />
            <ApSelect value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ width: 100 }}>
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
            </ApSelect>
          </div>
          {suggestions.length > 0 && (
            <div
              style={{
                position: 'absolute',
                left: 18,
                right: 18,
                marginTop: 6,
                background: AP.card,
                border: `1px solid ${AP.line2}`,
                borderRadius: 11,
                overflow: 'hidden',
                zIndex: 10,
                boxShadow: '0 14px 34px rgba(0,0,0,.55)',
                maxHeight: 200,
                overflowY: 'auto',
              }}
            >
              {suggestions.map((s) => (
                <button
                  key={s.user_id}
                  onClick={() => addMember(s.username)}
                  disabled={busy}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 9,
                    padding: '9px 13px',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontFamily: AP.sans,
                    fontSize: 13,
                    color: AP.ink,
                  }}
                >
                  <span
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 99,
                      background: AP.lumenBg,
                      border: `1px solid ${AP.lumenLine}`,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontFamily: AP.sans,
                      fontSize: 11,
                      fontWeight: 600,
                      color: AP.lumenSoft,
                      textTransform: 'uppercase',
                    }}
                  >
                    {s.username.charAt(0)}
                  </span>
                  {s.username}
                  <span style={{ marginLeft: 'auto', fontFamily: AP.mono, fontSize: 10, color: AP.ink3 }}>
                    add as {newRole}
                  </span>
                </button>
              ))}
            </div>
          )}
          {query.trim() && suggestions.length === 0 && !busy && (
            <span style={{ display: 'block', marginTop: 7, fontFamily: AP.sans, fontSize: 11, color: AP.ink4 }}>
              No matching users
            </span>
          )}
        </div>
      )}

      {error && (
        <div style={{ padding: '10px 18px', flex: '0 0 auto' }}>
          <ErrorBanner onDismiss={() => setError('')}>{error}</ErrorBanner>
        </div>
      )}

      <div className="ap-scroll" style={{ flex: 1, minHeight: 120, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {loading ? (
          <div style={{ padding: 14, fontFamily: AP.mono, fontSize: 12, color: AP.ink3 }}>loading…</div>
        ) : (
          members.map((m) => (
            <div
              key={m.user_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 11,
                padding: '10px 12px',
                borderRadius: 11,
                background: AP.card,
                border: `1px solid ${AP.line2}`,
              }}
            >
              <span
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 99,
                  background: 'rgba(255,255,255,.05)',
                  border: `1px solid ${AP.line2}`,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontFamily: AP.sans,
                  fontSize: 12,
                  fontWeight: 600,
                  color: AP.ink2,
                  textTransform: 'uppercase',
                  flex: '0 0 auto',
                }}
              >
                {(m.username ?? '?').charAt(0)}
              </span>
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  fontFamily: AP.sans,
                  fontSize: 13.5,
                  color: AP.ink,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {m.username}
              </span>
              {m.role === 'owner' || !canManage ? (
                <RoleBadge role={m.role} />
              ) : (
                <>
                  <ApSelect
                    value={m.role}
                    onChange={(e) => changeRole(m.user_id, e.target.value)}
                    style={{ width: 92, padding: '5px 8px', fontSize: 12 }}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="editor">Editor</option>
                  </ApSelect>
                  <button
                    onClick={() => removeMember(m.user_id)}
                    title="Revoke access"
                    style={{
                      width: 26,
                      height: 26,
                      borderRadius: 7,
                      background: 'transparent',
                      border: 'none',
                      color: AP.ink4,
                      cursor: 'pointer',
                      fontSize: 13,
                      flex: '0 0 auto',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = STATUS.err.c)}
                    onMouseLeave={(e) => (e.currentTarget.style.color = AP.ink4)}
                  >
                    ✕
                  </button>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </Modal>
  );
}

/* ── Workspace Card ───────────────────────────────────────────── */

function WsCard({ workspace, pipelines, onOpen, onEdit, onDelete, onScan, onMembers, scanning }) {
  const linked = pipelines.filter((p) => workspace.pipeline_ids?.includes(p._id));
  const myRole = workspace.my_role ?? 'owner';
  const canEdit = myRole === 'owner' || myRole === 'editor';
  const canManage = myRole === 'owner';
  const health = workspace.active ? 'ok' : 'idle';

  return (
    <div
      className="ap-cell"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 15,
        padding: 18,
        borderRadius: 15,
        background: AP.card,
        border: `1px solid ${workspace.active ? AP.emberLine : AP.line2}`,
        boxShadow: workspace.active ? `0 0 0 1px ${AP.emberLine}, 0 0 22px rgba(239,147,85,.1)` : 'none',
        opacity: workspace.active ? 1 : 0.75,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
          <Dot c={workspace.active ? AP.ember : AP.ink4} size={9} glow={workspace.active} />
          <span
            style={{
              fontFamily: AP.sans,
              fontSize: 16,
              fontWeight: 600,
              color: AP.ink,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {workspace.name}
          </span>
          {myRole !== 'owner' && <RoleBadge role={myRole} />}
        </div>
        <HealthPill state={health} label={workspace.active ? 'Watching' : 'Paused'} sm />
      </div>

      <div
        style={{
          fontFamily: AP.mono,
          fontSize: 11,
          color: AP.ink3,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        title={workspace.workspace_path}
      >
        {workspace.workspace_path}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
        <StatBlock label="Pipelines" value={linked.length} accent />
        <StatBlock label="File types" value={(workspace.extensions ?? []).length} />
        <StatBlock
          label="Added"
          value={workspace.created_at ? new Date(workspace.created_at).toLocaleDateString() : '—'}
        />
      </div>

      {linked.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          {linked.map((p) => (
            <span
              key={p._id}
              style={{
                fontFamily: AP.mono,
                fontSize: 10,
                color: AP.lumenSoft,
                padding: '2px 8px',
                borderRadius: 6,
                background: AP.lumenBg,
                border: `1px solid ${AP.lumenLine}`,
                whiteSpace: 'nowrap',
              }}
            >
              ◇ {p.name}
            </span>
          ))}
        </div>
      )}

      <div style={{ height: 1, background: AP.line }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <ActBtn
            onClick={() => onScan(workspace._id)}
            disabled={scanning || !workspace.active || !canEdit || !(workspace.pipeline_ids ?? []).length}
            title={
              !canEdit
                ? 'Viewers cannot trigger scans'
                : !workspace.active
                ? 'Workspace is paused'
                : !(workspace.pipeline_ids ?? []).length
                ? 'Attach at least one pipeline before scanning'
                : 'Trigger an immediate scan of this folder'
            }
          >
            {scanning ? '⟳ Scanning…' : '⟳ Scan'}
          </ActBtn>
          <ActBtn onClick={() => onMembers(workspace)} title="Manage members">
            ◫ Members
          </ActBtn>
          {canEdit && (
            <ActBtn onClick={() => onEdit(workspace)} title="Edit workspace">
              ✎
            </ActBtn>
          )}
          {canManage && (
            <ActBtn onClick={() => onDelete(workspace._id)} title="Delete workspace">
              🗑
            </ActBtn>
          )}
        </div>
        <button
          onClick={() => onOpen(workspace._id)}
          style={{
            fontFamily: AP.sans,
            fontSize: 12.5,
            fontWeight: 600,
            color: AP.lumenSoft,
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            flex: '0 0 auto',
          }}
        >
          Open ›
        </button>
      </div>
    </div>
  );
}

/* ── Main View ────────────────────────────────────────────────── */

function ImageUploadView() {
  const navigate = useNavigate();
  const [workspaces, setWorkspaces] = useState([]);
  const [pipelines, setPipelines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [drawer, setDrawer] = useState(null); // null | 'new' | workspace object
  const [membersFor, setMembersFor] = useState(null);
  const [scanning, setScanning] = useState(null);
  const [filter, setFilter] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [wsRes, plRes] = await Promise.all([axios.get(`${API}/workspaces`), axios.get(`${API}/pipelines`)]);
      setWorkspaces(wsRes.data);
      setPipelines(plRes.data);
    } catch {
      setError('Failed to load workspaces');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

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
    } catch (err) {
      setError(errorMessage(err, 'Scan trigger failed'));
    } finally {
      setScanning(null);
    }
  };

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return workspaces;
    return workspaces.filter((w) => w.name?.toLowerCase().includes(q) || w.workspace_path?.toLowerCase().includes(q));
  }, [workspaces, filter]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', color: AP.ink, overflow: 'hidden' }}>
      <ControlHeader
        breadcrumb="Control Room"
        title="Workspaces"
        count={`${workspaces.length} space${workspaces.length === 1 ? '' : 's'}`}
        actions={
          <>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '7px 11px',
                borderRadius: 9,
                background: AP.card,
                border: `1px solid ${AP.line2}`,
                width: 210,
              }}
            >
              <MagIcon size={15} c={AP.ink3} />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter workspaces"
                style={{
                  flex: 1,
                  minWidth: 0,
                  fontFamily: AP.sans,
                  fontSize: 13,
                  color: AP.ink,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                }}
              />
            </div>
            <LumenBtn onClick={() => setDrawer('new')}>+ New workspace</LumenBtn>
          </>
        }
      />

      <div className="ap-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 22 }}>
        {error && (
          <div style={{ marginBottom: 14 }}>
            <ErrorBanner onDismiss={() => setError('')}>{error}</ErrorBanner>
          </div>
        )}

        {loading ? (
          <div style={{ padding: 40, fontFamily: AP.mono, fontSize: 12, color: AP.ink3 }}>loading…</div>
        ) : visible.length === 0 ? (
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
            <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 14, fontWeight: 600, color: AP.ink2 }}>
              {filter ? 'No workspaces match your filter' : 'No workspaces yet'}
            </p>
            {!filter && (
              <>
                <p style={{ margin: 0, fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3 }}>
                  Create one to start watching a folder for images.
                </p>
                <LumenBtn onClick={() => setDrawer('new')}>+ New workspace</LumenBtn>
              </>
            )}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(310px, 1fr))', gap: 14 }}>
            {visible.map((w) => (
              <WsCard
                key={w._id}
                workspace={w}
                pipelines={pipelines}
                scanning={scanning === w._id}
                onOpen={(id) => navigate(`/workspaces/${id}`)}
                onEdit={(ws) => setDrawer(ws)}
                onDelete={handleDelete}
                onScan={handleScan}
                onMembers={(ws) => setMembersFor(ws)}
              />
            ))}
          </div>
        )}
      </div>

      {drawer && (
        <WorkspaceDrawer
          workspace={drawer === 'new' ? null : drawer}
          pipelines={pipelines}
          onSave={handleSave}
          onClose={() => setDrawer(null)}
        />
      )}
      {membersFor && <MembersModal workspace={membersFor} onClose={() => setMembersFor(null)} />}
    </div>
  );
}

export default ImageUploadView;
