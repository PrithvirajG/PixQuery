// PipelinesView — Aperture hi-fi Pipelines (node-chain builder), linear variant.
// Left: pipeline list rail. Center: vertical stage editor. Right: node inspector
// with the shared-pipeline warning (a pipeline can be attached to many workspaces).
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { errorMessage } from '../lib/apiError';
import {
  AP,
  STATUS,
  Dot,
  GhostBtn,
  LumenBtn,
  ActBtn,
  Chip,
  Eyebrow,
  ControlHeader,
  ApInput,
  ApSelect,
} from '../aperture/kit';
import PipelineGraphCanvas from '../components/PipelineGraphCanvas';

const API = 'http://localhost:8000';

const NODE_TYPES = [
  'object_detection',
  'captioning',
  'embedding',
  'ocr',
  'resize',
  'grayscale',
  'image_write',
  'classification',
  'face_detection',
];

const KIND_STYLE = {
  model: { c: AP.lumenSoft, bg: AP.lumenBg2, line: AP.lumenLine, icon: '✦' },
  proc: { c: AP.ink, bg: AP.cardHi, line: AP.line2, icon: '◧' },
  io: { c: AP.ink2, bg: AP.card, line: AP.line2, icon: '▢' },
};

// classify a node type for styling: model nodes glow Lumen
function kindOf(nodeType) {
  if (['object_detection', 'captioning', 'embedding', 'ocr', 'classification', 'face_detection'].includes(nodeType))
    return 'model';
  if (['resize', 'grayscale', 'image_write'].includes(nodeType)) return 'proc';
  return 'io';
}

function styleForType(nodeType) {
  return KIND_STYLE[kindOf(nodeType)];
}

function shortId(id) {
  return String(id ?? '').slice(0, 8);
}

const uid = () =>
  (window.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}-${Date.now()}`);

// Normalize a loaded pipeline into a graph the canvas can render: every node gets
// a stable node_id + canvas position, and a definition with no stored edges (e.g.
// a legacy linear one) is chained so it shows as a straight line.
function toGraph(p) {
  const nodes = (p.nodes ?? []).map((n, i) => ({
    node_id: n.node_id || uid(),
    pipeline_node_id: n.pipeline_node_id,
    config_overrides: n.config_overrides ?? {},
    position: n.position && typeof n.position.x === 'number' ? n.position : { x: 60, y: 40 + i * 96 },
  }));
  let edges = (p.edges ?? []).map((e) => ({
    edge_id: e.edge_id || uid(),
    from_node_id: e.from_node_id,
    to_node_id: e.to_node_id,
    from_output: e.from_output ?? null,
    to_input: e.to_input ?? null,
  }));
  if (!edges.length && nodes.length > 1) {
    edges = nodes.slice(1).map((n, i) => ({
      edge_id: uid(), from_node_id: nodes[i].node_id, to_node_id: n.node_id,
      from_output: null, to_input: null,
    }));
  }
  return { nodes, edges };
}

// Would adding from→to create a cycle? Walk forward from `to`; a cycle exists if
// we can already reach `from`.
function wouldCycle(edges, from, to) {
  const adj = {};
  edges.forEach((e) => { (adj[e.from_node_id] ||= []).push(e.to_node_id); });
  const stack = [to];
  const seen = new Set();
  while (stack.length) {
    const cur = stack.pop();
    if (cur === from) return true;
    if (seen.has(cur)) continue;
    seen.add(cur);
    (adj[cur] || []).forEach((nxt) => stack.push(nxt));
  }
  return false;
}

/* ── workspace reference chip ─────────────────────────────────── */
function WsChip({ name }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontFamily: AP.mono,
        fontSize: 9.5,
        color: AP.ember,
        padding: '2px 6px',
        borderRadius: 6,
        whiteSpace: 'nowrap',
        background: AP.emberBg,
        border: `1px solid ${AP.emberLine}`,
      }}
    >
      <Dot c={AP.ember} size={4} /> {name}
    </span>
  );
}

/* ── new node modal ───────────────────────────────────────────── */
function NewNodeModal({ onCreate, onClose }) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    node_type: NODE_TYPES[0],
    context_inputs: 'image',
    context_outputs: '',
    default_config: '{}',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    let cfg;
    try {
      cfg = JSON.parse(form.default_config || '{}');
    } catch {
      setError('Default config must be valid JSON');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await onCreate({
        name: form.name.trim(),
        description: form.description.trim(),
        node_type: form.node_type,
        context_inputs: form.context_inputs.split(',').map((s) => s.trim()).filter(Boolean),
        context_outputs: form.context_outputs.split(',').map((s) => s.trim()).filter(Boolean),
        config_schema: {},
        default_config: cfg,
      });
      onClose();
    } catch (err) {
      setError(errorMessage(err, 'Create failed'));
    } finally {
      setBusy(false);
    }
  };

  const label = { fontFamily: AP.mono, fontSize: 10.5, letterSpacing: '.09em', textTransform: 'uppercase', color: AP.ink3 };

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
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(3,4,8,0.7)', backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: 460,
          background: AP.panel,
          border: `1px solid ${AP.line2}`,
          borderRadius: 16,
          padding: 20,
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          boxShadow: '0 24px 60px rgba(0,0,0,.6)',
        }}
      >
        <div style={{ fontFamily: AP.sans, fontSize: 15, fontWeight: 600, color: AP.ink }}>New library node</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={label}>Name</span>
          <ApInput autoFocus value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="objects-precise" />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={label}>Stage type</span>
          <ApSelect value={form.node_type} onChange={(e) => setForm((f) => ({ ...f, node_type: e.target.value }))}>
            {NODE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </ApSelect>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={label}>Description</span>
          <ApInput value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="optional" />
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={label}>Inputs (csv)</span>
            <ApInput value={form.context_inputs} onChange={(e) => setForm((f) => ({ ...f, context_inputs: e.target.value }))} style={{ fontFamily: AP.mono, fontSize: 12 }} />
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={label}>Outputs (csv)</span>
            <ApInput value={form.context_outputs} onChange={(e) => setForm((f) => ({ ...f, context_outputs: e.target.value }))} style={{ fontFamily: AP.mono, fontSize: 12 }} />
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={label}>Default config (JSON)</span>
          <textarea
            value={form.default_config}
            onChange={(e) => setForm((f) => ({ ...f, default_config: e.target.value }))}
            rows={4}
            style={{
              fontFamily: AP.mono,
              fontSize: 12,
              color: AP.ink,
              background: AP.card,
              border: `1px solid ${AP.line2}`,
              borderRadius: 9,
              padding: '9px 11px',
              outline: 'none',
              resize: 'vertical',
            }}
          />
        </div>
        {error && <span style={{ fontFamily: AP.sans, fontSize: 12, color: STATUS.err.c }}>{error}</span>}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <GhostBtn onClick={onClose}>Cancel</GhostBtn>
          <LumenBtn onClick={submit} disabled={busy}>
            {busy ? 'Creating…' : 'Create node'}
          </LumenBtn>
        </div>
      </div>
    </div>,
    document.body
  );
}

/* ── main view ────────────────────────────────────────────────── */

function ModelManagementView() {
  const location = useLocation();
  const [pipelines, setPipelines] = useState([]);
  const [nodeLibrary, setNodeLibrary] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [editPipeline, setEditPipeline] = useState(null); // {name, description, nodes}
  const [dirty, setDirty] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [showPalette, setShowPalette] = useState(false);
  const [showNewNode, setShowNewNode] = useState(false);
  const [creatingNew, setCreatingNew] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [configText, setConfigText] = useState('{}');
  const [configErr, setConfigErr] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [plRes, nodesRes, wsRes] = await Promise.all([
        axios.get(`${API}/pipelines`),
        axios.get(`${API}/pipeline-nodes`),
        axios.get(`${API}/workspaces`),
      ]);
      setPipelines(plRes.data);
      setNodeLibrary(nodesRes.data);
      setWorkspaces(wsRes.data);
      return plRes.data;
    } catch {
      setError('Failed to load data');
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const selectPipeline = useCallback((p) => {
    const { nodes, edges } = toGraph(p);
    setSelectedId(p._id);
    setEditPipeline({
      name: p.name,
      description: p.description ?? '',
      nodes,
      edges,
      extract_metadata: p.extract_metadata ?? false,
    });
    setDirty(false);
    setSelectedNodeId(nodes[0]?.node_id ?? null);
  }, []);

  useEffect(() => {
    loadData().then((pls) => {
      const target = location.state?.selectPipeline;
      const pick = (target && pls.find((p) => p._id === target)) || pls[0];
      if (pick) selectPipeline(pick);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // keep the config textarea in sync with the selected node
  useEffect(() => {
    const node = editPipeline?.nodes?.find((n) => n.node_id === selectedNodeId);
    if (!node) {
      setConfigText('{}');
      return;
    }
    setConfigText(JSON.stringify(node.config_overrides ?? {}, null, 2));
    setConfigErr('');
  }, [selectedNodeId, editPipeline]);

  const nodeDefOf = useCallback(
    (chainEntry) => nodeLibrary.find((d) => d._id === chainEntry.pipeline_node_id),
    [nodeLibrary]
  );

  const attachedWorkspaces = useMemo(
    () => workspaces.filter((w) => (w.pipeline_ids ?? []).includes(selectedId)),
    [workspaces, selectedId]
  );

  const mutate = (fn) => {
    setEditPipeline((ep) => fn(ep));
    setDirty(true);
  };

  const handleSave = async () => {
    if (!selectedId || !editPipeline) return;
    setSaving(true);
    try {
      await axios.put(`${API}/pipelines/${selectedId}`, editPipeline);
      await loadData();
      setDirty(false);
    } catch {
      setError('Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const res = await axios.post(`${API}/pipelines`, { name: newName.trim(), nodes: [] });
      setCreatingNew(false);
      setNewName('');
      const pls = await loadData();
      const created = pls.find((p) => p._id === res.data._id) ?? res.data;
      selectPipeline(created);
    } catch {
      setError('Create failed');
    }
  };

  const handleDuplicate = async (p) => {
    try {
      const { nodes, edges } = toGraph(p);
      // Fresh node ids for the copy; rewrite edges through the id map.
      const idMap = {};
      const copyNodes = nodes.map((n) => {
        const nid = uid();
        idMap[n.node_id] = nid;
        return { node_id: nid, pipeline_node_id: n.pipeline_node_id, config_overrides: n.config_overrides, position: n.position };
      });
      const copyEdges = edges.map((e) => ({
        from_node_id: idMap[e.from_node_id], to_node_id: idMap[e.to_node_id],
        from_output: e.from_output, to_input: e.to_input,
      }));
      const res = await axios.post(`${API}/pipelines`, {
        name: `${p.name}-copy`,
        description: p.description ?? '',
        extract_metadata: p.extract_metadata ?? false,
        nodes: copyNodes,
        edges: copyEdges,
      });
      const pls = await loadData();
      const created = pls.find((x) => x._id === res.data._id) ?? res.data;
      selectPipeline(created);
    } catch {
      setError('Duplicate failed');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this pipeline?')) return;
    try {
      await axios.delete(`${API}/pipelines/${id}`);
      if (selectedId === id) {
        setSelectedId(null);
        setEditPipeline(null);
        setSelectedNodeId(null);
      }
      await loadData();
    } catch {
      setError('Delete failed');
    }
  };

  // Add a node to the graph. Stagger its position off the last node so it doesn't
  // land on top of an existing card; leave it unconnected (user wires it).
  const addNode = (nodeDef) => {
    const newId = uid();
    mutate((ep) => {
      const last = ep.nodes[ep.nodes.length - 1];
      const position = last
        ? { x: (last.position?.x ?? 60) + 60, y: (last.position?.y ?? 40) + 110 }
        : { x: 60, y: 40 };
      return {
        ...ep,
        nodes: [...ep.nodes, { node_id: newId, pipeline_node_id: nodeDef._id, config_overrides: {}, position }],
      };
    });
    setShowPalette(false);
    setSelectedNodeId(newId);
  };

  const removeNode = (nodeId) => {
    mutate((ep) => ({
      ...ep,
      nodes: ep.nodes.filter((n) => n.node_id !== nodeId),
      edges: ep.edges.filter((e) => e.from_node_id !== nodeId && e.to_node_id !== nodeId),
    }));
    setSelectedNodeId((cur) => (cur === nodeId ? null : cur));
  };

  const moveNode = (nodeId, position) => {
    mutate((ep) => ({
      ...ep,
      nodes: ep.nodes.map((n) => (n.node_id === nodeId ? { ...n, position } : n)),
    }));
  };

  const addEdge = ({ from_node_id, to_node_id }) => {
    if (!editPipeline) return;
    const exists = editPipeline.edges.some(
      (e) => e.from_node_id === from_node_id && e.to_node_id === to_node_id
    );
    if (exists) return;
    if (wouldCycle(editPipeline.edges, from_node_id, to_node_id)) {
      setError('That connection would create a cycle.');
      return;
    }
    mutate((ep) => ({
      ...ep,
      edges: [...ep.edges, { edge_id: uid(), from_node_id, to_node_id, from_output: null, to_input: null }],
    }));
  };

  const removeEdge = (edge) => {
    mutate((ep) => ({ ...ep, edges: ep.edges.filter((e) => e !== edge && e.edge_id !== edge.edge_id) }));
  };

  const applyConfig = () => {
    let cfg;
    try {
      cfg = JSON.parse(configText || '{}');
    } catch {
      setConfigErr('Invalid JSON');
      return;
    }
    setConfigErr('');
    mutate((ep) => ({
      ...ep,
      nodes: ep.nodes.map((n) => (n.node_id === selectedNodeId ? { ...n, config_overrides: cfg } : n)),
    }));
  };

  const handleCreateNode = async (payload) => {
    await axios.post(`${API}/pipeline-nodes`, payload);
    await loadData();
  };

  const handleDeleteNode = async (id) => {
    if (!window.confirm('Delete this custom node from the library?')) return;
    try {
      await axios.delete(`${API}/pipeline-nodes/${id}`);
      await loadData();
    } catch (err) {
      setError(errorMessage(err, 'Node delete failed'));
    }
  };

  const selected = pipelines.find((p) => p._id === selectedId);
  const stage = editPipeline?.nodes?.find((n) => n.node_id === selectedNodeId) ?? null;
  const stageDef = stage ? nodeDefOf(stage) : null;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', color: AP.ink, overflow: 'hidden' }}>
      <ControlHeader
        breadcrumb="Control Room"
        title="Pipelines"
        count={`${pipelines.length} defined`}
        actions={
          <>
            {dirty && (
              <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ember }}>unsaved changes</span>
            )}
            <GhostBtn onClick={() => selected && handleDuplicate(selected)} disabled={!selected}>
              ⧉ Duplicate
            </GhostBtn>
            <GhostBtn onClick={() => setShowNewNode(true)}>+ New node</GhostBtn>
            {dirty ? (
              <LumenBtn onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : '✓ Save pipeline'}
              </LumenBtn>
            ) : (
              <LumenBtn onClick={() => setCreatingNew(true)}>+ New pipeline</LumenBtn>
            )}
          </>
        }
      />

      {error && (
        <div
          style={{
            margin: '10px 22px 0',
            padding: '9px 13px',
            borderRadius: 10,
            background: STATUS.err.bg,
            border: `1px solid ${STATUS.err.line}`,
            fontFamily: AP.sans,
            fontSize: 12.5,
            color: STATUS.err.c,
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          {error}
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', color: STATUS.err.c, cursor: 'pointer' }}>
            ✕
          </button>
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        {/* ── left rail: pipeline list ── */}
        <div
          className="ap-scroll"
          style={{
            width: 268,
            flex: '0 0 auto',
            borderRight: `1px solid ${AP.line}`,
            overflowY: 'auto',
            padding: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <Eyebrow>All pipelines</Eyebrow>
            <span style={{ fontFamily: AP.mono, fontSize: 10, color: AP.ink3 }}>{pipelines.length}</span>
          </div>

          {creatingNew && (
            <div style={{ display: 'flex', gap: 7 }}>
              <ApInput
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                placeholder="pipeline name"
                style={{ flex: 1, fontSize: 12.5, padding: '7px 9px' }}
              />
              <ActBtn accent onClick={handleCreate}>
                ✓
              </ActBtn>
              <ActBtn onClick={() => setCreatingNew(false)}>✕</ActBtn>
            </div>
          )}

          {loading ? (
            <span style={{ fontFamily: AP.mono, fontSize: 12, color: AP.ink3, padding: 8 }}>loading…</span>
          ) : (
            pipelines.map((p) => {
              const sel = p._id === selectedId;
              const wsList = workspaces.filter((w) => (w.pipeline_ids ?? []).includes(p._id));
              return (
                <div
                  key={p._id}
                  className="ap-facet"
                  onClick={() => selectPipeline(p)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 7,
                    padding: '11px 12px',
                    borderRadius: 11,
                    cursor: 'pointer',
                    background: sel ? AP.lumenBg : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${sel ? AP.lumenLine : AP.line}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                      <span style={{ fontSize: 11, color: sel ? AP.lumen : AP.ink4 }}>◇</span>
                      <span
                        style={{
                          fontFamily: AP.sans,
                          fontSize: 13.5,
                          fontWeight: 600,
                          color: sel ? AP.ink : AP.ink2,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {p.name}
                      </span>
                    </span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flex: '0 0 auto' }}>
                      <button
                        title="Duplicate pipeline"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDuplicate(p);
                        }}
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: 6,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 12,
                          color: sel ? AP.lumenSoft : AP.ink3,
                          background: 'rgba(255,255,255,0.04)',
                          border: `1px solid ${AP.line2}`,
                        }}
                      >
                        ⧉
                      </button>
                      <button
                        title="Delete pipeline"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(p._id);
                        }}
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: 6,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 11,
                          color: AP.ink4,
                          background: 'rgba(255,255,255,0.04)',
                          border: `1px solid ${AP.line2}`,
                        }}
                      >
                        ✕
                      </button>
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 18 }}>
                    <span style={{ fontFamily: AP.mono, fontSize: 10, color: sel ? AP.lumenSoft : AP.ink3 }}>
                      #{shortId(p._id)}
                    </span>
                    <span style={{ fontFamily: AP.mono, fontSize: 10, color: AP.ink4 }}>·</span>
                    <span style={{ fontFamily: AP.mono, fontSize: 10, color: AP.ink3 }}>
                      {(p.nodes ?? []).length} stage{(p.nodes ?? []).length === 1 ? '' : 's'}
                    </span>
                  </div>
                  {wsList.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingLeft: 18 }}>
                      {wsList.map((w) => (
                        <WsChip key={w._id} name={w.name} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* ── center: graph editor ── */}
        <div className="ap-scroll" style={{ flex: 1, minWidth: 0, overflow: 'auto', padding: '22px 28px' }}>
          {!editPipeline ? (
            <div style={{ padding: 30, fontFamily: AP.sans, fontSize: 13, color: AP.ink3 }}>
              Select a pipeline on the left, or create a new one.
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 20, flexWrap: 'wrap' }}>
                <Chip reason={editPipeline.name} score={`#${shortId(selectedId)}`} variant="pill" />
                <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>
                  {editPipeline.nodes.length} stage{editPipeline.nodes.length === 1 ? '' : 's'}
                  {attachedWorkspaces.length > 0 &&
                    ` · attached to ${attachedWorkspaces.length} workspace${attachedWorkspaces.length === 1 ? '' : 's'}`}
                </span>
              </div>

              {/* pipeline-wide settings (not a stage) */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  marginBottom: 22,
                  padding: '11px 14px',
                  borderRadius: 11,
                  background: AP.card,
                  border: `1px solid ${AP.line2}`,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontFamily: AP.sans, fontSize: 13, fontWeight: 600, color: AP.ink }}>
                    Extract EXIF &amp; GPS metadata
                  </div>
                  <div style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3, marginTop: 2 }}>
                    Pipeline-wide · reads dimensions, camera &amp; GPS from the original file
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={!!editPipeline.extract_metadata}
                  title="Toggle metadata extraction"
                  onClick={() => mutate((ep) => ({ ...ep, extract_metadata: !ep.extract_metadata }))}
                  style={{
                    position: 'relative',
                    width: 42,
                    height: 24,
                    borderRadius: 99,
                    flex: '0 0 auto',
                    cursor: 'pointer',
                    padding: 0,
                    background: editPipeline.extract_metadata ? AP.lumen : 'rgba(255,255,255,0.06)',
                    border: `1px solid ${editPipeline.extract_metadata ? AP.lumenLine : AP.line2}`,
                    transition: 'background .15s',
                  }}
                >
                  <span
                    style={{
                      position: 'absolute',
                      top: 2,
                      left: editPipeline.extract_metadata ? 20 : 2,
                      width: 18,
                      height: 18,
                      borderRadius: 99,
                      background: '#fff',
                      transition: 'left .15s',
                    }}
                  />
                </button>
              </div>

              {/* add node + palette + wiring hint */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <button
                    onClick={() => setShowPalette((v) => !v)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 7,
                      padding: '9px 13px',
                      borderRadius: 10,
                      cursor: 'pointer',
                      fontFamily: AP.sans,
                      fontSize: 13,
                      fontWeight: 500,
                      color: AP.lumenSoft,
                      background: AP.lumenBg,
                      border: `1px dashed ${AP.lumenLine}`,
                    }}
                  >
                    + Add stage
                  </button>
                  {showPalette && (
                    <div
                      style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        marginTop: 8,
                        width: 340,
                        maxHeight: 320,
                        overflowY: 'auto',
                        background: AP.card,
                        border: `1px solid ${AP.line2}`,
                        borderRadius: 12,
                        padding: 8,
                        zIndex: 30,
                        boxShadow: '0 16px 40px rgba(0,0,0,.55)',
                      }}
                      className="ap-scroll"
                    >
                      {nodeLibrary.map((d) => {
                        const k = KIND_STYLE[kindOf(d.node_type)];
                        const custom = d.owner_id !== 'system';
                        return (
                          <div
                            key={d._id}
                            style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '8px 9px', borderRadius: 9 }}
                          >
                            <button
                              onClick={() => addNode(d)}
                              style={{
                                flex: 1,
                                minWidth: 0,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 9,
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                textAlign: 'left',
                              }}
                            >
                              <span
                                style={{
                                  width: 26,
                                  height: 26,
                                  borderRadius: 7,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontSize: 12,
                                  color: k.c,
                                  background: 'rgba(255,255,255,0.05)',
                                  border: `1px solid ${k.line}`,
                                  flex: '0 0 auto',
                                }}
                              >
                                {k.icon}
                              </span>
                              <span style={{ minWidth: 0 }}>
                                <span style={{ display: 'block', fontFamily: AP.sans, fontSize: 13, fontWeight: 600, color: AP.ink }}>
                                  {d.name}
                                </span>
                                <span style={{ fontFamily: AP.mono, fontSize: 10, color: AP.ink3 }}>{d.node_type}</span>
                              </span>
                            </button>
                            {custom && (
                              <button
                                title="Delete custom node"
                                onClick={() => handleDeleteNode(d._id)}
                                style={{
                                  width: 22,
                                  height: 22,
                                  borderRadius: 6,
                                  cursor: 'pointer',
                                  background: 'transparent',
                                  border: 'none',
                                  color: AP.ink4,
                                  fontSize: 11,
                                  flex: '0 0 auto',
                                }}
                              >
                                ✕
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>
                  drag a node's right port → another node's left port to connect · {editPipeline.edges.length} connection{editPipeline.edges.length === 1 ? '' : 's'}
                </span>
              </div>

              {/* graph canvas */}
              <PipelineGraphCanvas
                nodes={editPipeline.nodes}
                edges={editPipeline.edges}
                nodeLibrary={nodeLibrary}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
                onMoveNode={moveNode}
                onAddEdge={addEdge}
                onRemoveEdge={removeEdge}
                onRemoveNode={removeNode}
                styleForType={styleForType}
              />
            </>
          )}
        </div>

        {/* ── right: node inspector ── */}
        <div
          className="ap-scroll"
          style={{
            width: 296,
            flex: '0 0 auto',
            borderLeft: `1px solid ${AP.line}`,
            overflowY: 'auto',
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 18,
            background: AP.panel,
          }}
        >
          {!stage || !stageDef ? (
            <span style={{ fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3, lineHeight: 1.5 }}>
              Select a stage to inspect its configuration.
            </span>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: AP.lumen }}>✦</span>
                <Eyebrow c={AP.lumenSoft}>Node · {stageDef.name}</Eyebrow>
              </div>

              {/* shared-pipeline warning */}
              {attachedWorkspaces.length > 1 && (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                    padding: '12px 13px',
                    borderRadius: 11,
                    background: AP.emberBg,
                    border: `1px solid ${AP.emberLine}`,
                  }}
                >
                  <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <span style={{ color: AP.ember, fontSize: 13, flex: '0 0 auto', lineHeight: 1.3 }}>⚠</span>
                    <span style={{ fontFamily: AP.sans, fontSize: 12, lineHeight: 1.45, color: AP.ink2 }}>
                      Editing <b style={{ color: AP.ink, fontWeight: 600 }}>{editPipeline.name}</b> affects{' '}
                      <b style={{ color: AP.ember, fontWeight: 600 }}>{attachedWorkspaces.length} workspaces</b>.
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, paddingLeft: 21 }}>
                    {attachedWorkspaces.map((w) => (
                      <WsChip key={w._id} name={w.name} />
                    ))}
                  </div>
                  <button
                    onClick={() => handleDuplicate(selected)}
                    style={{
                      marginLeft: 21,
                      alignSelf: 'flex-start',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      fontFamily: AP.sans,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      padding: '6px 11px',
                      borderRadius: 8,
                      color: '#fff',
                      background: AP.ember,
                      border: 'none',
                      boxShadow: '0 1px 8px rgba(239,147,85,.35)',
                    }}
                  >
                    ⧉ Duplicate to edit safely
                  </button>
                </div>
              )}

              {[
                ['Node name', stageDef.name],
                ['Stage type', stageDef.node_type],
                ['Inputs', (stageDef.context_inputs ?? []).join(', ') || '—'],
                ['Outputs', (stageDef.context_outputs ?? []).join(', ') || '—'],
              ].map(([l, v]) => (
                <div key={l} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <Eyebrow>{l}</Eyebrow>
                  <div
                    style={{
                      padding: '9px 11px',
                      borderRadius: 9,
                      background: AP.card,
                      border: `1px solid ${AP.line2}`,
                      fontFamily: AP.mono,
                      fontSize: 12.5,
                      color: AP.ink,
                      wordBreak: 'break-word',
                    }}
                  >
                    {v}
                  </div>
                </div>
              ))}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Eyebrow>Config overrides (JSON)</Eyebrow>
                <textarea
                  value={configText}
                  onChange={(e) => setConfigText(e.target.value)}
                  rows={7}
                  spellCheck={false}
                  style={{
                    fontFamily: AP.mono,
                    fontSize: 11.5,
                    lineHeight: 1.6,
                    color: AP.ink,
                    background: AP.card,
                    border: `1px solid ${configErr ? STATUS.err.line : AP.line2}`,
                    borderRadius: 9,
                    padding: '10px 11px',
                    outline: 'none',
                    resize: 'vertical',
                  }}
                />
                {configErr && <span style={{ fontFamily: AP.sans, fontSize: 11.5, color: STATUS.err.c }}>{configErr}</span>}
                <ActBtn accent onClick={applyConfig}>
                  Apply to stage
                </ActBtn>
              </div>

              {Object.keys(stageDef.default_config ?? {}).length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <Eyebrow>Default config</Eyebrow>
                  <pre
                    style={{
                      margin: 0,
                      padding: '11px 12px',
                      borderRadius: 9,
                      background: AP.card,
                      border: `1px solid ${AP.line2}`,
                      fontFamily: AP.mono,
                      fontSize: 11,
                      color: AP.ink2,
                      lineHeight: 1.7,
                      overflowX: 'auto',
                    }}
                  >
                    {JSON.stringify(stageDef.default_config, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {showNewNode && <NewNodeModal onCreate={handleCreateNode} onClose={() => setShowNewNode(false)} />}
    </div>
  );
}

export default ModelManagementView;
