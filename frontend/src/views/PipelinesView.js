import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';

const NODE_CATEGORY_COLORS = {
  object_detection: 'violet',
  face_detection: 'pink',
  segmentation: 'indigo',
  classification: 'blue',
  captioning: 'cyan',
  embedding: 'teal',
  grayscale: 'slate',
  compress: 'orange',
  crop: 'amber',
  resize: 'yellow',
  draw_boxes: 'green',
};

function categoryColor(type) {
  const color = NODE_CATEGORY_COLORS[type] ?? 'slate';
  const map = {
    violet: 'bg-violet-900/40 text-violet-300 border-violet-700/50',
    pink: 'bg-pink-900/40 text-pink-300 border-pink-700/50',
    indigo: 'bg-indigo-900/40 text-indigo-300 border-indigo-700/50',
    blue: 'bg-blue-900/40 text-blue-300 border-blue-700/50',
    cyan: 'bg-cyan-900/40 text-cyan-300 border-cyan-700/50',
    teal: 'bg-teal-900/40 text-teal-300 border-teal-700/50',
    slate: 'bg-slate-700/40 text-slate-300 border-slate-600/50',
    orange: 'bg-orange-900/40 text-orange-300 border-orange-700/50',
    amber: 'bg-amber-900/40 text-amber-300 border-amber-700/50',
    yellow: 'bg-yellow-900/40 text-yellow-300 border-yellow-700/50',
    green: 'bg-green-900/40 text-green-300 border-green-700/50',
  };
  return map[color] ?? map.slate;
}

/* ── Add-Node Modal ─────────────────────────────────────────────── */
function AddNodeModal({ nodeLibrary, existingContextKeys, onAdd, onClose }) {
  const [search, setSearch] = useState('');
  const filtered = nodeLibrary.filter(n =>
    n.name.toLowerCase().includes(search.toLowerCase()) ||
    n.node_type.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-h-[80vh]">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <h3 className="font-bold text-slate-200">Add Node</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-4">
          <input
            autoFocus
            type="text"
            placeholder="Search nodes…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-slate-800/60 border border-slate-700/60 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-violet-500/50 transition-all"
          />
        </div>
        <div className="flex-1 overflow-y-auto px-4 pb-4 flex flex-col gap-2">
          {filtered.map(node => {
            const missing = node.context_inputs.filter(k => k !== 'image' && !existingContextKeys.has(k));
            const incompatible = missing.length > 0;
            return (
              <button
                key={node._id}
                onClick={() => onAdd(node)}
                className={`flex flex-col gap-2 p-4 rounded-xl border text-left transition-all ${
                  incompatible
                    ? 'bg-red-950/20 border-red-900/50 hover:border-red-700/50'
                    : 'bg-slate-800/40 border-slate-700/40 hover:border-violet-500/40 hover:bg-slate-800/70'
                }`}
              >
                <div className="flex items-center gap-2 justify-between">
                  <span className="font-semibold text-sm text-slate-200">{node.name}</span>
                  {incompatible && (
                    <span className="text-[10px] font-bold text-red-400 bg-red-950/50 border border-red-800/50 px-2 py-0.5 rounded-full">
                      Missing: {missing.join(', ')}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-400">{node.description}</p>
                <div className="flex gap-2 flex-wrap">
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${categoryColor(node.node_type)}`}>
                    {node.node_type}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    in: {node.context_inputs.join(', ') || '—'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    out: {node.context_outputs.join(', ') || '—'}
                  </span>
                </div>
              </button>
            );
          })}
          {filtered.length === 0 && (
            <p className="text-sm text-slate-500 text-center py-8">No nodes match your search</p>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Node Chain Editor ──────────────────────────────────────────── */
function NodeChain({ nodes, nodeLibrary, onRemove, onMoveUp, onMoveDown, onEditConfig }) {
  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center text-slate-600 border-2 border-dashed border-slate-800 rounded-2xl">
        <svg className="w-10 h-10 mb-3 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
        </svg>
        <p className="text-sm">No nodes yet — click <span className="text-violet-400 font-semibold">+ Add Node</span> below</p>
      </div>
    );
  }

  const contextKeys = new Set(['image']);
  return (
    <div className="flex flex-col gap-1">
      {nodes.map((node, i) => {
        const def = nodeLibrary.find(n => n._id === node.pipeline_node_id);
        const missing = def ? def.context_inputs.filter(k => k !== 'image' && !contextKeys.has(k)) : [];
        if (def) def.context_outputs.forEach(k => contextKeys.add(k));

        return (
          <React.Fragment key={node.node_id ?? i}>
            <div className={`flex items-start gap-3 p-4 rounded-xl border bg-slate-900/60 backdrop-blur transition-all ${
              missing.length > 0 ? 'border-red-800/60' : 'border-slate-800/60'
            }`}>
              {/* Drag handle / order */}
              <span className="text-xs text-slate-600 font-mono mt-1 w-5 text-center">{i + 1}</span>

              <div className="flex-1 flex flex-col gap-2 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm text-slate-200">{def?.name ?? node.pipeline_node_id}</span>
                  {def && (
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${categoryColor(def.node_type)}`}>
                      {def.node_type}
                    </span>
                  )}
                  {missing.length > 0 && (
                    <span className="text-[10px] font-bold text-red-400 bg-red-950/50 border border-red-800/50 px-2 py-0.5 rounded-full">
                      ⚠ Missing: {missing.join(', ')}
                    </span>
                  )}
                </div>
                {def && (
                  <div className="flex gap-3 text-[11px] text-slate-500">
                    <span>in: <span className="text-slate-400">{def.context_inputs.join(', ') || '—'}</span></span>
                    <span className="text-slate-700">→</span>
                    <span>out: <span className="text-slate-400">{def.context_outputs.join(', ') || '—'}</span></span>
                  </div>
                )}
                {Object.keys(node.config_overrides ?? {}).length > 0 && (
                  <div className="text-[11px] text-slate-500 font-mono bg-slate-800/40 px-3 py-1.5 rounded-lg">
                    {JSON.stringify(node.config_overrides)}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => onMoveUp(i)}
                  disabled={i === 0}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800 disabled:opacity-30 transition-all"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                  </svg>
                </button>
                <button
                  onClick={() => onMoveDown(i)}
                  disabled={i === nodes.length - 1}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800 disabled:opacity-30 transition-all"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                <button
                  onClick={() => onEditConfig(i)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-violet-400 hover:bg-slate-800 transition-all"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  onClick={() => onRemove(i)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-red-400 hover:bg-slate-800 transition-all"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
            {i < nodes.length - 1 && (
              <div className="flex justify-center py-0.5">
                <div className="w-px h-4 bg-slate-700" />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

/* ── Config Edit Drawer ─────────────────────────────────────────── */
function ConfigDrawer({ node, nodeDef, onSave, onClose }) {
  const [overrides, setOverrides] = useState(
    JSON.stringify(node.config_overrides ?? {}, null, 2)
  );
  const [err, setErr] = useState('');

  const handleSave = () => {
    try {
      const parsed = JSON.parse(overrides);
      onSave(parsed);
      onClose();
    } catch {
      setErr('Invalid JSON');
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-96 bg-slate-900 border-l border-slate-800 flex flex-col shadow-2xl">
      <div className="p-5 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h3 className="font-bold text-slate-200 text-sm">{nodeDef?.name ?? 'Node Config'}</h3>
          <p className="text-xs text-slate-500 mt-0.5">Override default configuration</p>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {nodeDef && (
        <div className="px-5 pt-4 pb-2">
          <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider mb-2">Default Config</p>
          <pre className="text-[11px] text-slate-400 bg-slate-800/50 rounded-xl p-3 overflow-auto max-h-24">
            {JSON.stringify(nodeDef.default_config, null, 2)}
          </pre>
        </div>
      )}

      <div className="flex-1 flex flex-col px-5 py-4 gap-3">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Config Overrides (JSON)</label>
        <textarea
          value={overrides}
          onChange={e => { setOverrides(e.target.value); setErr(''); }}
          rows={10}
          className="flex-1 bg-slate-800/60 border border-slate-700/60 rounded-xl p-3 text-sm font-mono text-slate-200 outline-none focus:border-violet-500/50 resize-none transition-all"
        />
        {err && <p className="text-xs text-red-400">{err}</p>}
      </div>

      <div className="p-5 border-t border-slate-800 flex gap-3">
        <button onClick={onClose} className="flex-1 px-4 py-2.5 rounded-xl border border-slate-700 text-sm font-semibold text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-all">
          Cancel
        </button>
        <button onClick={handleSave} className="flex-1 px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold transition-all">
          Save
        </button>
      </div>
    </div>
  );
}

/* ── Pipeline Node Library Tab ──────────────────────────────────── */
function NodeLibraryTab({ nodeLibrary, onCreateNode, onDeleteNode }) {
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: '', description: '', node_type: '', context_inputs: '', context_outputs: '',
    config_schema: '{}', default_config: '{}',
  });
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        description: form.description,
        node_type: form.node_type,
        context_inputs: form.context_inputs.split(',').map(s => s.trim()).filter(Boolean),
        context_outputs: form.context_outputs.split(',').map(s => s.trim()).filter(Boolean),
        config_schema: JSON.parse(form.config_schema || '{}'),
        default_config: JSON.parse(form.default_config || '{}'),
      };
      await onCreateNode(payload);
      setShowCreate(false);
      setForm({ name: '', description: '', node_type: '', context_inputs: '', context_outputs: '', config_schema: '{}', default_config: '{}' });
    } catch {
      alert('Failed to create node. Check JSON fields.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-300 text-sm">Pipeline Node Library</h3>
        <button
          onClick={() => setShowCreate(v => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-violet-600/20 border border-violet-500/30 text-violet-300 text-xs font-semibold hover:bg-violet-600/30 transition-all"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Node
        </button>
      </div>

      {showCreate && (
        <div className="bg-slate-800/40 border border-slate-700/60 rounded-2xl p-5 flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[['name', 'Name'], ['node_type', 'Node Type'], ['context_inputs', 'Context Inputs (comma-sep)'], ['context_outputs', 'Context Outputs (comma-sep)']].map(([k, label]) => (
              <div key={k} className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-slate-400">{label}</label>
                <input
                  type="text"
                  value={form[k]}
                  onChange={e => setForm(v => ({ ...v, [k]: e.target.value }))}
                  className="bg-slate-800/60 border border-slate-700/60 rounded-xl px-3 py-2 text-sm text-slate-200 outline-none focus:border-violet-500/50 transition-all"
                />
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Description</label>
            <input
              type="text"
              value={form.description}
              onChange={e => setForm(v => ({ ...v, description: e.target.value }))}
              className="bg-slate-800/60 border border-slate-700/60 rounded-xl px-3 py-2 text-sm text-slate-200 outline-none focus:border-violet-500/50 transition-all"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[['config_schema', 'Config Schema (JSON)'], ['default_config', 'Default Config (JSON)']].map(([k, label]) => (
              <div key={k} className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-slate-400">{label}</label>
                <textarea
                  rows={4}
                  value={form[k]}
                  onChange={e => setForm(v => ({ ...v, [k]: e.target.value }))}
                  className="bg-slate-800/60 border border-slate-700/60 rounded-xl px-3 py-2 text-sm font-mono text-slate-200 outline-none focus:border-violet-500/50 resize-none transition-all"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button onClick={() => setShowCreate(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-slate-700 text-sm font-semibold text-slate-400 hover:text-slate-200 transition-all">Cancel</button>
            <button onClick={handleCreate} disabled={saving} className="flex-1 px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold disabled:opacity-50 transition-all">
              {saving ? 'Creating…' : 'Create Node'}
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {nodeLibrary.map(node => (
          <div key={node._id} className="flex flex-col gap-2 p-4 bg-slate-900/60 border border-slate-800 rounded-2xl backdrop-blur">
            <div className="flex items-start justify-between gap-2">
              <span className="font-semibold text-sm text-slate-200">{node.name}</span>
              {node.owner_id !== 'system' && (
                <button
                  onClick={() => onDeleteNode(node._id)}
                  className="text-slate-600 hover:text-red-400 transition-colors shrink-0"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">{node.description}</p>
            <div className="flex gap-1.5 flex-wrap mt-auto">
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${categoryColor(node.node_type)}`}>
                {node.node_type}
              </span>
              {node.owner_id === 'system' && (
                <span className="text-[10px] text-slate-500 bg-slate-800/60 px-2 py-0.5 rounded-full border border-slate-700/50">system</span>
              )}
            </div>
            <div className="flex gap-3 text-[10px] text-slate-600 mt-1">
              <span>in: {node.context_inputs?.join(', ') || '—'}</span>
              <span>out: {node.context_outputs?.join(', ') || '—'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Main View ──────────────────────────────────────────────────── */
function ModelManagementView() {
  const [tab, setTab] = useState('pipelines'); // 'pipelines' | 'library'
  const [pipelines, setPipelines] = useState([]);
  const [nodeLibrary, setNodeLibrary] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [editPipeline, setEditPipeline] = useState(null); // {name, description, nodes}
  const [showAddNode, setShowAddNode] = useState(false);
  const [configEdit, setConfigEdit] = useState(null); // {index}
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newName, setNewName] = useState('');
  const [creatingNew, setCreatingNew] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [plRes, nodesRes] = await Promise.all([
        axios.get(`${API}/pipelines`),
        axios.get(`${API}/pipeline-nodes`),
      ]);
      setPipelines(plRes.data);
      setNodeLibrary(nodesRes.data);
    } catch {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const selectPipeline = (p) => {
    setSelectedId(p._id);
    setEditPipeline({ name: p.name, description: p.description ?? '', nodes: p.nodes ?? [] });
  };

  const handleSavePipeline = async () => {
    if (!selectedId) return;
    setSaving(true);
    try {
      await axios.put(`${API}/pipelines/${selectedId}`, editPipeline);
      await loadData();
    } catch {
      setError('Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleCreatePipeline = async () => {
    if (!newName.trim()) return;
    try {
      const res = await axios.post(`${API}/pipelines`, { name: newName.trim(), nodes: [] });
      setCreatingNew(false);
      setNewName('');
      await loadData();
      selectPipeline(res.data);
    } catch {
      setError('Create failed');
    }
  };

  const handleDeletePipeline = async (id) => {
    if (!window.confirm('Delete this pipeline?')) return;
    try {
      await axios.delete(`${API}/pipelines/${id}`);
      if (selectedId === id) { setSelectedId(null); setEditPipeline(null); }
      await loadData();
    } catch {
      setError('Delete failed');
    }
  };

  const addNode = (nodeDef) => {
    setEditPipeline(ep => ({
      ...ep,
      nodes: [
        ...ep.nodes,
        { pipeline_node_id: nodeDef._id, config_overrides: {} },
      ],
    }));
    setShowAddNode(false);
  };

  const removeNode = (i) => {
    setEditPipeline(ep => ({ ...ep, nodes: ep.nodes.filter((_, idx) => idx !== i) }));
  };

  const moveNode = (i, dir) => {
    setEditPipeline(ep => {
      const nodes = [...ep.nodes];
      const swap = i + dir;
      if (swap < 0 || swap >= nodes.length) return ep;
      [nodes[i], nodes[swap]] = [nodes[swap], nodes[i]];
      return { ...ep, nodes };
    });
  };

  const saveNodeConfig = (i, cfg) => {
    setEditPipeline(ep => {
      const nodes = [...ep.nodes];
      nodes[i] = { ...nodes[i], config_overrides: cfg };
      return { ...ep, nodes };
    });
  };

  const handleCreateNode = async (payload) => {
    await axios.post(`${API}/pipeline-nodes`, payload);
    await loadData();
  };

  const handleDeleteNode = async (id) => {
    if (!window.confirm('Delete this custom node?')) return;
    try {
      await axios.delete(`${API}/pipeline-nodes/${id}`);
      await loadData();
    } catch {
      setError('Delete failed');
    }
  };

  const existingContextKeys = (() => {
    const keys = new Set(['image']);
    if (!editPipeline) return keys;
    for (const n of editPipeline.nodes) {
      const def = nodeLibrary.find(d => d._id === n.pipeline_node_id);
      if (def) def.context_outputs?.forEach(k => keys.add(k));
    }
    return keys;
  })();

  return (
    <div className="flex flex-col gap-5 pb-10">
      {/* Header + Tabs */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Pipelines</h2>
          <p className="text-sm text-slate-500 mt-0.5">Build and manage image processing pipelines</p>
        </div>
        <div className="flex gap-2">
          {[['pipelines', 'Pipelines'], ['library', 'Node Library']].map(([t, label]) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-xl text-sm font-semibold border transition-all ${
                tab === t
                  ? 'bg-violet-600/20 border-violet-500/40 text-violet-300'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
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
      ) : tab === 'library' ? (
        <NodeLibraryTab nodeLibrary={nodeLibrary} onCreateNode={handleCreateNode} onDeleteNode={handleDeleteNode} />
      ) : (
        <div className="flex gap-4" style={{ minHeight: '560px' }}>
          {/* Left panel */}
          <div className="w-64 shrink-0 flex flex-col gap-2.5">
            <button
              onClick={() => setCreatingNew(true)}
              className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl
                         bg-gradient-to-r from-violet-600/20 to-blue-600/20
                         border border-violet-500/30 text-violet-300 text-sm font-semibold
                         hover:from-violet-600/30 hover:to-blue-600/30 transition-all"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Pipeline
            </button>

            {creatingNew && (
              <div className="flex gap-2">
                <input
                  autoFocus
                  type="text"
                  placeholder="Pipeline name…"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleCreatePipeline(); if (e.key === 'Escape') setCreatingNew(false); }}
                  className="flex-1 bg-slate-800/60 border border-violet-500/40 rounded-xl px-3 py-2.5
                             text-sm text-slate-200 outline-none focus:ring-2 focus:ring-violet-500/10 transition-all"
                />
                <button
                  onClick={handleCreatePipeline}
                  className="w-10 rounded-xl bg-violet-600 text-white text-base font-semibold
                             hover:bg-violet-500 transition-all flex items-center justify-center"
                >✓</button>
              </div>
            )}

            {/* Scrollable pipeline list */}
            <div className="flex flex-col gap-2 overflow-y-auto flex-1" style={{ maxHeight: '520px' }}>
              {pipelines.map(p => (
                <div
                  key={p._id}
                  onClick={() => selectPipeline(p)}
                  className={`group flex items-start justify-between gap-2 px-3 py-3 rounded-xl border
                              cursor-pointer transition-all ${
                    selectedId === p._id
                      ? 'bg-violet-900/20 border-violet-500/40 shadow-[0_0_14px_rgba(139,92,246,0.1)]'
                      : 'bg-slate-900/50 border-slate-800 hover:border-slate-700 hover:bg-slate-900/70'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-slate-200 truncate">{p.name}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {(p.nodes ?? []).length} node{(p.nodes ?? []).length !== 1 ? 's' : ''}
                    </p>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); handleDeletePipeline(p._id); }}
                    className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400
                               transition-all shrink-0 p-0.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7
                               m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              ))}
              {pipelines.length === 0 && (
                <p className="text-sm text-slate-600 text-center py-10">No pipelines yet</p>
              )}
            </div>
          </div>

          {/* Right panel */}
          <div className="flex-1 min-w-0">
            {editPipeline ? (
              <div className="flex flex-col gap-0 bg-slate-900/40 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur">
                {/* Name & description header */}
                <div className="px-5 pt-5 pb-4 border-b border-slate-800/60 flex flex-col gap-2">
                  <input
                    type="text"
                    value={editPipeline.name}
                    onChange={e => setEditPipeline(ep => ({ ...ep, name: e.target.value }))}
                    className="bg-transparent border-b border-slate-700/60 focus:border-violet-500/60
                               pb-1.5 text-lg font-bold text-slate-100 outline-none transition-colors w-full"
                  />
                  <input
                    type="text"
                    value={editPipeline.description}
                    onChange={e => setEditPipeline(ep => ({ ...ep, description: e.target.value }))}
                    placeholder="Description (optional)"
                    className="bg-transparent text-sm text-slate-500 placeholder-slate-600
                               outline-none w-full"
                  />
                </div>

                {/* Node chain area */}
                <div className="flex flex-col gap-3 p-5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      Node Chain
                    </span>
                    <span className="text-[11px] text-slate-600 tabular-nums">
                      {editPipeline.nodes.length} node{editPipeline.nodes.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <NodeChain
                    nodes={editPipeline.nodes}
                    nodeLibrary={nodeLibrary}
                    onRemove={removeNode}
                    onMoveUp={i => moveNode(i, -1)}
                    onMoveDown={i => moveNode(i, 1)}
                    onEditConfig={i => setConfigEdit({ index: i })}
                  />
                  <button
                    onClick={() => setShowAddNode(true)}
                    className="flex items-center justify-center gap-2 py-3 rounded-xl
                               border-2 border-dashed border-slate-700/60
                               text-slate-500 hover:text-violet-400 hover:border-violet-700/50
                               transition-all text-sm font-semibold"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add Node
                  </button>
                </div>

                {/* Save footer */}
                <div className="flex gap-3 px-5 py-4 border-t border-slate-800/60 bg-slate-900/40">
                  <button
                    onClick={handleSavePipeline}
                    disabled={saving}
                    className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-blue-600
                               hover:from-violet-500 hover:to-blue-500 text-white text-sm font-semibold
                               disabled:opacity-50 transition-all shadow-[0_0_16px_rgba(139,92,246,0.2)]"
                  >
                    {saving ? 'Saving…' : 'Save Pipeline'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full py-24 text-center
                              bg-slate-900/20 border border-slate-800/60 rounded-2xl text-slate-600">
                <svg className="w-10 h-10 mb-3 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                        d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
                <p className="text-sm text-slate-500">
                  Select a pipeline from the left, or create a new one
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {showAddNode && (
        <AddNodeModal
          nodeLibrary={nodeLibrary}
          existingContextKeys={existingContextKeys}
          onAdd={addNode}
          onClose={() => setShowAddNode(false)}
        />
      )}

      {configEdit !== null && editPipeline && (
        <ConfigDrawer
          node={editPipeline.nodes[configEdit.index]}
          nodeDef={nodeLibrary.find(n => n._id === editPipeline.nodes[configEdit.index]?.pipeline_node_id)}
          onSave={cfg => saveNodeConfig(configEdit.index, cfg)}
          onClose={() => setConfigEdit(null)}
        />
      )}
    </div>
  );
}

export default ModelManagementView;
