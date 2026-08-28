// WorkspaceDetailView — Aperture hi-fi Workspace Details.
// Shows the space's pipelines split into Attached / Available; each attached pipeline
// offers Edit (→ Pipelines page) and Statistics (→ run stats for this workspace).
// Job state is aggregated client-side from /stats/jobs/recent — a dedicated
// per-workspace stats endpoint is a known backend gap.
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useParams, useNavigate } from 'react-router-dom';
import { errorMessage } from '../lib/apiError';
import { API_BASE as API } from '../lib/apiBase';
import {
  AP,
  STATUS,
  Dot,
  GhostBtn,
  LumenBtn,
  ActBtn,
  Toggle,
  Eyebrow,
  HealthPill,
  Bar,
  StatBlock,
  MetricRing,
} from '../aperture/kit';
const STLABEL = { run: 'Running', ok: 'Succeeded', err: 'Failed', queue: 'Queued', idle: 'Never run' };

function pipeState(agg) {
  if (!agg || agg.total === 0) return 'idle';
  if (agg.processing > 0) return 'run';
  if (agg.queued > 0) return 'queue';
  if (agg.failed > 0) return 'err';
  return 'ok';
}

function PipeRow({ pipeline, agg, attached, onToggle, onEdit, onStats }) {
  const state = attached ? pipeState(agg) : 'idle';
  const s = STATUS[state] ?? STATUS.idle;
  const total = agg?.total ?? 0;
  const done = agg?.completed ?? 0;
  const prog = total ? done / total : 0;
  const nodeCount = (pipeline.nodes ?? []).length;
  const running = state === 'run';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '15px 17px',
        borderRadius: 13,
        background: running ? AP.lumenBg : AP.card,
        opacity: attached ? 1 : 0.66,
        border: `1px solid ${running ? AP.lumenLine : AP.line2}`,
        boxShadow: running ? '0 0 22px rgba(124,108,247,.12)' : 'none',
      }}
    >
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: attached ? s.c : AP.ink4 }}>◇</span>
          <span style={{ fontFamily: AP.sans, fontSize: 15, fontWeight: 600, color: AP.ink }}>{pipeline.name}</span>
          <span
            style={{
              fontFamily: AP.mono,
              fontSize: 10.5,
              color: AP.ink3,
              padding: '1px 6px',
              borderRadius: 6,
              background: 'rgba(255,255,255,0.04)',
              border: `1px solid ${AP.line2}`,
            }}
            title={pipeline._id}
          >
            #{String(pipeline._id).slice(0, 8)}
          </span>
          <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>
            {nodeCount} node{nodeCount === 1 ? '' : 's'}
          </span>
        </div>

        {running ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, maxWidth: 460 }}>
            <Bar v={prog} pulse />
            <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3, flex: '0 0 auto' }}>
              {done}/{total}
            </span>
            <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: s.c, flex: '0 0 auto' }}>
              {agg.processing} in flight
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <HealthPill state={state} label={STLABEL[state]} sm />
            {attached && total > 0 && (
              <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: state === 'err' ? s.c : AP.ink3 }}>
                {state === 'err' ? `${agg.failed} failed · ` : ''}
                {done}/{total} completed
              </span>
            )}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flex: '0 0 auto' }}>
        <Toggle on={attached} onClick={onToggle} title={attached ? 'Detach from this workspace' : 'Attach to this workspace'} />
        <ActBtn onClick={onEdit}>✎ Edit</ActBtn>
        <ActBtn accent onClick={onStats} disabled={!attached} title={!attached ? 'Attach the pipeline first' : undefined}>
          ▤ Statistics
        </ActBtn>
      </div>
    </div>
  );
}

export default function WorkspaceDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [ws, setWs] = useState(null);
  const [pipelines, setPipelines] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [wsRes, plRes, jobsRes] = await Promise.all([
        axios.get(`${API}/workspaces/${id}`),
        axios.get(`${API}/pipelines`),
        axios.get(`${API}/stats/jobs/recent?limit=500`),
      ]);
      setWs(wsRes.data);
      setPipelines(plRes.data);
      setJobs(jobsRes.data.filter((j) => j.workspace_id === id));
    } catch {
      setError('Failed to load workspace');
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000); // light polling — no push channel yet
    return () => clearInterval(t);
  }, [load]);

  // Aggregate recent jobs per pipeline: {total, completed, failed, queued, processing}
  const aggByPipeline = useMemo(() => {
    const m = {};
    for (const j of jobs) {
      const k = j.pipeline_id;
      if (!m[k]) m[k] = { total: 0, completed: 0, failed: 0, queued: 0, processing: 0 };
      m[k].total += 1;
      if (j.status === 'completed') m[k].completed += 1;
      else if (j.status === 'failed') m[k].failed += 1;
      else if (j.status === 'queued') m[k].queued += 1;
      else if (j.status === 'processing') m[k].processing += 1;
    }
    return m;
  }, [jobs]);

  const toggleAttach = async (pipelineId) => {
    const current = ws.pipeline_ids ?? [];
    const next = current.includes(pipelineId) ? current.filter((p) => p !== pipelineId) : [...current, pipelineId];
    try {
      const res = await axios.put(`${API}/workspaces/${id}`, { pipeline_ids: next });
      setWs(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Update failed'));
    }
  };

  if (error && !ws) {
    return (
      <div style={{ padding: 40, fontFamily: AP.sans, fontSize: 14, color: STATUS.err.c }}>
        {error}{' '}
        <button
          onClick={() => navigate('/workspaces')}
          style={{ color: AP.lumenSoft, background: 'none', border: 'none', cursor: 'pointer' }}
        >
          ‹ Workspaces
        </button>
      </div>
    );
  }
  if (!ws) {
    return <div style={{ padding: 40, fontFamily: AP.mono, fontSize: 13, color: AP.ink3 }}>loading…</div>;
  }

  const attachedIds = ws.pipeline_ids ?? [];
  const attached = pipelines.filter((p) => attachedIds.includes(p._id));
  const available = pipelines.filter((p) => !attachedIds.includes(p._id));

  const totals = Object.values(aggByPipeline).reduce(
    (a, b) => ({
      total: a.total + b.total,
      completed: a.completed + b.completed,
      failed: a.failed + b.failed,
      processing: a.processing + b.processing,
    }),
    { total: 0, completed: 0, failed: 0, processing: 0 }
  );
  const coverage = totals.total ? totals.completed / totals.total : 0;
  const anyRunning = totals.processing > 0;
  const health = !ws.active ? 'idle' : anyRunning ? 'run' : totals.failed > 0 ? 'warn' : 'ok';
  const healthLabel = { ok: 'Healthy', run: 'Indexing', warn: 'Degraded', idle: 'Paused' }[health];
  const lastJob = jobs.length
    ? jobs.reduce((a, b) => ((a.updated_at ?? '') > (b.updated_at ?? '') ? a : b))
    : null;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', color: AP.ink, overflow: 'hidden' }}>
      {/* header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          padding: '15px 24px',
          borderBottom: `1px solid ${AP.line}`,
          background: AP.panel,
          flex: '0 0 auto',
        }}
      >
        <button
          onClick={() => navigate('/workspaces')}
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
          <span style={{ fontSize: 15 }}>‹</span> Workspaces
        </button>
        <div style={{ width: 1, height: 18, background: AP.line2 }} />
        <Dot c={AP.ember} size={9} glow={ws.active} />
        <span style={{ fontFamily: AP.sans, fontSize: 18, fontWeight: 600, color: AP.ink }}>{ws.name}</span>
        <HealthPill state={health} label={healthLabel} sm />
        <div style={{ flex: 1 }} />
        <GhostBtn onClick={() => navigate(`/search?workspace_id=${id}`)}>↗ Open in Search</GhostBtn>
        <LumenBtn onClick={() => navigate('/pipelines')}>+ New pipeline</LumenBtn>
      </div>

      <div
        className="ap-scroll"
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: 24,
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
        }}
      >
        {error && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 10,
              background: STATUS.err.bg,
              border: `1px solid ${STATUS.err.line}`,
              fontFamily: AP.sans,
              fontSize: 12.5,
              color: STATUS.err.c,
            }}
          >
            {error}
          </div>
        )}

        {/* stat strip */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 28,
            padding: '18px 22px',
            borderRadius: 15,
            background: AP.card,
            border: `1px solid ${AP.line2}`,
            flexWrap: 'wrap',
          }}
        >
          <MetricRing v={coverage} size={58} label="JOBS" />
          <StatBlock label="Recent jobs" value={totals.total} sub={`${totals.completed} completed`} />
          <div style={{ width: 1, height: 38, background: AP.line }} />
          <StatBlock label="Failed" value={totals.failed} sub={totals.failed ? 'retry from Statistics' : 'all clear'} />
          <div style={{ width: 1, height: 38, background: AP.line }} />
          <StatBlock label="Pipelines" value={`${attached.length} attached`} accent />
          <div style={{ width: 1, height: 38, background: AP.line }} />
          <StatBlock
            label="Last activity"
            value={lastJob?.updated_at ? new Date(lastJob.updated_at).toLocaleTimeString() : '—'}
            sub={lastJob ? `job ${lastJob.status}` : 'no jobs yet'}
          />
          <div style={{ width: 1, height: 38, background: AP.line }} />
          <StatBlock
            label="Path"
            value={
              <span style={{ fontFamily: AP.mono, fontSize: 12 }} title={ws.workspace_path}>
                {ws.workspace_path?.length > 30 ? `…${ws.workspace_path.slice(-28)}` : ws.workspace_path}
              </span>
            }
          />
        </div>

        {/* Attached pipelines */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Eyebrow c={AP.lumenSoft}>Attached pipelines</Eyebrow>
            <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>{attached.length}</span>
            <span style={{ flex: 1, height: 1, background: AP.line }} />
          </div>
          {attached.length === 0 ? (
            <span style={{ fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3 }}>
              No pipelines attached — new files will be ingested but not processed.
            </span>
          ) : (
            attached.map((p) => (
              <PipeRow
                key={p._id}
                pipeline={p}
                agg={aggByPipeline[p._id]}
                attached
                onToggle={() => toggleAttach(p._id)}
                onEdit={() => navigate('/pipelines', { state: { selectPipeline: p._id } })}
                onStats={() => navigate(`/workspaces/${id}/pipelines/${p._id}/stats`)}
              />
            ))
          )}
        </div>

        {/* Available (not attached) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Eyebrow>Available</Eyebrow>
            <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>{available.length}</span>
            <span style={{ flex: 1, height: 1, background: AP.line }} />
          </div>
          {available.map((p) => (
            <PipeRow
              key={p._id}
              pipeline={p}
              agg={aggByPipeline[p._id]}
              attached={false}
              onToggle={() => toggleAttach(p._id)}
              onEdit={() => navigate('/pipelines', { state: { selectPipeline: p._id } })}
              onStats={() => {}}
            />
          ))}
          {available.length === 0 && (
            <span style={{ fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3 }}>
              All your pipelines are attached to this workspace.
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start', color: AP.ink3 }}>
          <span style={{ color: AP.lumen, fontSize: 12, flex: '0 0 auto' }}>✦</span>
          <span style={{ fontFamily: AP.sans, fontSize: 12, lineHeight: 1.45 }}>
            <b style={{ color: AP.ink2, fontWeight: 600 }}>Edit</b> opens the pipeline definition ·{' '}
            <b style={{ color: AP.ink2, fontWeight: 600 }}>Statistics</b> shows job progress and failures for this
            workspace.
          </span>
        </div>
      </div>
    </div>
  );
}
