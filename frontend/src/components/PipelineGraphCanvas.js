// PipelineGraphCanvas — hand-rolled node-graph editor (no external deps).
// Renders pipeline nodes as draggable cards on a scrollable canvas, with SVG
// bezier edges between an output port (right) and an input port (left). Drag a
// node to move it; drag from a node's output port onto another node's input port
// to wire an edge; click an edge's ✕ badge to remove it. All mutations bubble up
// through callbacks so PipelinesView owns the pipeline state.
import React, { useRef, useState, useCallback, useMemo } from 'react';
import { AP } from '../aperture/kit';

const NODE_W = 188;
const NODE_H = 58;

const outPort = (p) => ({ x: p.x + NODE_W, y: p.y + NODE_H / 2 });
const inPort = (p) => ({ x: p.x, y: p.y + NODE_H / 2 });

function edgePath(x1, y1, x2, y2) {
  const c = Math.max(40, Math.abs(x2 - x1) * 0.5);
  return `M ${x1} ${y1} C ${x1 + c} ${y1}, ${x2 - c} ${y2}, ${x2} ${y2}`;
}

function Port({ side, onMouseDown, onMouseUp, active }) {
  return (
    <div
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
      title={side === 'out' ? 'Drag to connect' : 'Drop to connect'}
      style={{
        position: 'absolute',
        top: NODE_H / 2 - 7,
        [side === 'out' ? 'right' : 'left']: -7,
        width: 14,
        height: 14,
        borderRadius: 99,
        cursor: 'crosshair',
        background: active ? AP.lumen : AP.card,
        border: `2px solid ${active ? AP.lumen : AP.line2}`,
        boxShadow: active ? `0 0 8px ${AP.lumen}` : 'none',
        zIndex: 3,
      }}
    />
  );
}

export default function PipelineGraphCanvas({
  nodes,
  edges,
  nodeLibrary,
  selectedNodeId,
  onSelectNode,
  onMoveNode,
  onAddEdge,
  onRemoveEdge,
  onRemoveNode,
  styleForType,
}) {
  const canvasRef = useRef(null);
  const [drag, setDrag] = useState(null); // { nodeId, dx, dy, x, y }
  const [pending, setPending] = useState(null); // { fromId, x, y }

  const defOf = useCallback(
    (n) => nodeLibrary.find((d) => d._id === n.pipeline_node_id),
    [nodeLibrary]
  );

  const toCanvas = useCallback((e) => {
    const r = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }, []);

  // Effective position for a node: live drag override, else its stored position.
  const posOf = useCallback(
    (n) => (drag && drag.nodeId === n.node_id ? { x: drag.x, y: drag.y } : n.position),
    [drag]
  );

  const nodePos = useMemo(() => {
    const m = {};
    nodes.forEach((n) => { m[n.node_id] = posOf(n); });
    return m;
  }, [nodes, posOf]);

  const width = Math.max(1400, ...nodes.map((n) => nodePos[n.node_id].x + NODE_W + 240));
  const height = Math.max(820, ...nodes.map((n) => nodePos[n.node_id].y + NODE_H + 240));

  const startNodeDrag = (e, n) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const p = toCanvas(e);
    setDrag({ nodeId: n.node_id, dx: p.x - n.position.x, dy: p.y - n.position.y, x: n.position.x, y: n.position.y });
    onSelectNode(n.node_id);
  };

  const startEdge = (e, n) => {
    e.stopPropagation();
    const p = toCanvas(e);
    setPending({ fromId: n.node_id, x: p.x, y: p.y });
  };

  const onMove = (e) => {
    if (drag) {
      const p = toCanvas(e);
      setDrag((d) => ({ ...d, x: Math.max(0, p.x - d.dx), y: Math.max(0, p.y - d.dy) }));
    } else if (pending) {
      const p = toCanvas(e);
      setPending((pd) => ({ ...pd, x: p.x, y: p.y }));
    }
  };

  const endOnCanvas = () => {
    if (drag) {
      onMoveNode(drag.nodeId, { x: Math.round(drag.x), y: Math.round(drag.y) });
      setDrag(null);
    }
    if (pending) setPending(null); // released on empty canvas → cancel
  };

  const dropOnInput = (e, n) => {
    if (!pending) return; // let node-drag commit at the canvas level
    e.stopPropagation();
    if (n.node_id !== pending.fromId) {
      onAddEdge({ from_node_id: pending.fromId, to_node_id: n.node_id });
    }
    setPending(null);
  };

  return (
    <div
      ref={canvasRef}
      onMouseMove={onMove}
      onMouseUp={endOnCanvas}
      onMouseLeave={() => { setDrag(null); setPending(null); }}
      onClick={(e) => { if (e.target === e.currentTarget) onSelectNode(null); }}
      style={{
        position: 'relative',
        width,
        height,
        // faint dot grid
        backgroundImage: `radial-gradient(${AP.line2} 1px, transparent 1px)`,
        backgroundSize: '22px 22px',
      }}
    >
      <svg width={width} height={height} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        {edges.map((edge) => {
          const from = nodePos[edge.from_node_id];
          const to = nodePos[edge.to_node_id];
          if (!from || !to) return null;
          const a = outPort(from);
          const b = inPort(to);
          return (
            <path
              key={edge.edge_id || `${edge.from_node_id}-${edge.to_node_id}`}
              d={edgePath(a.x, a.y, b.x, b.y)}
              fill="none"
              stroke={AP.lumenLine}
              strokeWidth={2}
            />
          );
        })}
        {pending && (() => {
          const from = nodePos[pending.fromId];
          if (!from) return null;
          const a = outPort(from);
          return (
            <path
              d={edgePath(a.x, a.y, pending.x, pending.y)}
              fill="none"
              stroke={AP.lumen}
              strokeWidth={2}
              strokeDasharray="5 4"
            />
          );
        })()}
      </svg>

      {/* edge delete badges (over the svg, clickable) */}
      {edges.map((edge) => {
        const from = nodePos[edge.from_node_id];
        const to = nodePos[edge.to_node_id];
        if (!from || !to) return null;
        const a = outPort(from);
        const b = inPort(to);
        const mx = (a.x + b.x) / 2;
        const my = (a.y + b.y) / 2;
        return (
          <button
            key={`del-${edge.edge_id || `${edge.from_node_id}-${edge.to_node_id}`}`}
            title="Remove connection"
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => { e.stopPropagation(); onRemoveEdge(edge); }}
            style={{
              position: 'absolute',
              left: mx - 9,
              top: my - 9,
              width: 18,
              height: 18,
              borderRadius: 99,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              color: AP.ink3,
              background: AP.card,
              border: `1px solid ${AP.line2}`,
              zIndex: 4,
            }}
          >
            ✕
          </button>
        );
      })}

      {/* node cards */}
      {nodes.map((n) => {
        const def = defOf(n);
        const p = nodePos[n.node_id];
        const sel = selectedNodeId === n.node_id;
        const st = styleForType ? styleForType(def?.node_type) : { c: AP.ink, line: AP.line2, icon: '▢' };
        return (
          <div
            key={n.node_id}
            onMouseDown={(e) => startNodeDrag(e, n)}
            onClick={(e) => { e.stopPropagation(); onSelectNode(n.node_id); }}
            style={{
              position: 'absolute',
              left: p.x,
              top: p.y,
              width: NODE_W,
              height: NODE_H,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '0 12px',
              borderRadius: 12,
              cursor: 'grab',
              userSelect: 'none',
              background: sel ? AP.lumenBg : AP.card,
              border: `1px solid ${sel ? AP.lumenLine : AP.line2}`,
              boxShadow: sel ? '0 0 16px rgba(124,108,247,.35)' : '0 6px 18px rgba(0,0,0,.35)',
              zIndex: sel ? 2 : 1,
            }}
          >
            <Port side="in" onMouseUp={(e) => dropOnInput(e, n)} active={!!pending && pending.fromId !== n.node_id} />
            <span
              style={{
                width: 30,
                height: 30,
                borderRadius: 8,
                flex: '0 0 auto',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 14,
                color: st.c,
                background: 'rgba(255,255,255,0.05)',
                border: `1px solid ${st.line}`,
              }}
            >
              {st.icon}
            </span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontFamily: AP.sans, fontSize: 13, fontWeight: 600, color: AP.ink, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {def?.name ?? 'unknown node'}
              </div>
              <div style={{ fontFamily: AP.mono, fontSize: 9.5, color: AP.ink3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {def?.node_type ?? n.pipeline_node_id}
              </div>
            </div>
            <button
              title="Remove node"
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => { e.stopPropagation(); onRemoveNode(n.node_id); }}
              style={{
                width: 20,
                height: 20,
                flex: '0 0 auto',
                borderRadius: 6,
                cursor: 'pointer',
                color: AP.ink4,
                background: 'rgba(255,255,255,0.04)',
                border: `1px solid ${AP.line2}`,
                fontSize: 10,
              }}
            >
              ✕
            </button>
            <Port side="out" onMouseDown={(e) => startEdge(e, n)} active={!!pending && pending.fromId === n.node_id} />
          </div>
        );
      })}

      {nodes.length === 0 && (
        <div style={{ position: 'absolute', top: 40, left: 40, fontFamily: AP.sans, fontSize: 13, color: AP.ink3 }}>
          No stages yet — add one from the palette, then drag between the ports to wire the graph.
        </div>
      )}
    </div>
  );
}
