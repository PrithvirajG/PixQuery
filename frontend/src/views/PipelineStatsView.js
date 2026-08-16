// PipelineStatsView — Aperture hi-fi Pipeline Statistics, scoped to one pipeline
// within one workspace. Live counters, the asset currently being processed, a
// failed-jobs list with retry, and an activity feed derived from job updates.
// Poll-based: the backend has no push channel or log stream yet (known gap).
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AP,
  STATUS,
  Dot,
  GhostBtn,
  ActBtn,
  Chip,
  Eyebrow,
  HealthPill,
  Bar,
  Counter,
} from '../aperture/kit';

const API = 'http://localhost:8000';

const LOG_COLOR = { queued: AP.ink3, processing: AP.lumenSoft, completed: STATUS.ok.c, failed: STATUS.err.c };

function shortId(id) {
  return String(id ?? '').slice(0, 8);
}

export default function PipelineStatsView() {
  const { id: workspaceId, pipelineId } = useParams();
  const navigate = useNavigate();
  const [ws, setWs] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState('');
  const [retrying, setRetrying] = useState({});

  const load = useCallback(async () => {
    try {
      const [wsRes, plRes, jobsRes] = await Promise.all([
        axios.get(`${API}/workspaces/${workspaceId}`),
        axios.get(`${API}/pipelines/${pipelineId}`),
        axios.get(`${API}/stats/jobs/recent?limit=500`),
      ]);
      setWs(wsRes.data);
      setPipeline(plRes.data);
      setJobs(jobsRes.data.filter((j) => j.workspace_id === workspaceId && j.pipeline_id === pipelineId));
    } catch {
      setError('Failed to load pipeline statistics');
    }
  }, [workspaceId, pipelineId]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const agg = useMemo(() => {
    const a = { total: jobs.length, completed: 0, failed: 0, queued: 0, processing: 0 };
    for (const j of jobs) {
      if (a[j.status] !== undefined) a[j.status] += 1;
    }
    return a;
  }, [jobs]);

  const prog = agg.total ? agg.completed / agg.total : 0;
  const running = agg.processing > 0;
  const state = running ? 'run' : agg.queued > 0 ? 'queue' : agg.failed > 0 ? 'err' : agg.total ? 'ok' : 'idle';
  const stateLabel = { run: 'Running', queue: 'Queued', err: 'Has failures', ok: 'Completed', idle: 'No jobs yet' }[state];

  const processing = jobs.filter((j) => j.status === 'processing');
  const failed = jobs.filter((j) => j.status === 'failed');

  // activity feed — newest first, derived from job status updates
  const feed = useMemo(
    () =>
      [...jobs]
        .sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))
        .slice(0, 40),
    [jobs]
  );

  const retryJob = async (jobId) => {
    setRetrying((r) => ({ ...r, [jobId]: true }));
    try {
      await axios.post(`${API}/jobs/${jobId}/requeue`);
      await load();
    } catch {
      setError('Retry failed');
    } finally {
      setRetrying((r) => ({ ...r, [jobId]: false }));
    }
  };

  const retryAll = async () => {
    for (const j of failed) {
      // sequential to keep the API happy; no bulk-requeue endpoint yet
      // eslint-disable-next-line no-await-in-loop
      await axios.post(`${API}/jobs/${j._id}/requeue`).catch(() => {});
    }
    await load();
  };

  if (!ws || !pipeline) {
    return (
      <div style={{ padding: 40, fontFamily: AP.mono, fontSize: 13, color: error ? STATUS.err.c : AP.ink3 }}>
        {error || 'loading…'}
      </div>
    );
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', color: AP.ink, overflow: 'hidden' }}>
      {/* header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 13,
          padding: '15px 24px',
          borderBottom: `1px solid ${AP.line}`,
          background: AP.panel,
          flex: '0 0 auto',
        }}
      >
        <button
          onClick={() => navigate(`/workspaces/${workspaceId}`)}
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
          <span style={{ fontSize: 15 }}>‹</span> {ws.name}
        </button>
        <div style={{ width: 1, height: 18, background: AP.line2 }} />
        <Chip reason={pipeline.name} score={`#${shortId(pipeline._id)}`} variant="pill" />
        <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>
          {(pipeline.nodes ?? []).length} stages · Statistics
        </span>
        <HealthPill state={state === 'idle' ? 'queue' : state} label={stateLabel} sm />
        <div style={{ flex: 1 }} />
        <GhostBtn disabled title="Pausing a running pipeline needs backend support — not available yet">
          ⏸ Pause
        </GhostBtn>
        <GhostBtn onClick={() => navigate('/pipelines', { state: { selectPipeline: pipelineId } })}>
          ✎ Edit pipeline
        </GhostBtn>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        {/* main */}
        <div
          className="ap-scroll"
          style={{
            flex: 1,
            minWidth: 0,
            overflowY: 'auto',
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          {error && (
            <div
              style={{
                padding: '9px 13px',
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

          {/* counters */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Counter label="Completed" value={agg.completed} sub={`of ${agg.total}`} c={STATUS.ok.c} accent={STATUS.ok} />
            <Counter label="Failed" value={agg.failed} sub="retryable" c={STATUS.err.c} accent={STATUS.err} />
            <Counter label="In progress" value={agg.processing} sub={`${agg.queued} queued`} c={AP.lumenSoft} accent={STATUS.run} />
            <Counter label="ETA" value="—" sub="needs job telemetry" />
          </div>

          {/* overall progress */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 9,
              padding: '16px 18px',
              borderRadius: 14,
              background: AP.card,
              border: `1px solid ${AP.line2}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Eyebrow c={AP.lumenSoft}>Overall progress</Eyebrow>
              <span style={{ fontFamily: AP.mono, fontSize: 12, color: AP.ink }}>{Math.round(prog * 100)}%</span>
            </div>
            <Bar v={prog} pulse={running} h={8} />
          </div>

          {/* currently processing */}
          {processing.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
              <Eyebrow c={AP.lumenSoft}>Now processing</Eyebrow>
              {processing.slice(0, 3).map((j) => (
                <div
                  key={j._id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16,
                    padding: 14,
                    borderRadius: 14,
                    background: AP.lumenBg,
                    border: `1px solid ${AP.lumenLine}`,
                  }}
                >
                  <div className="ap-photo" style={{ width: 96, height: 72, borderRadius: 10, background: AP.cardHi, flex: '0 0 auto' }}>
                    <img
                      src={`${API}/images/${j.asset_id}/thumbnail`}
                      alt=""
                      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e) => {
                        e.target.style.display = 'none';
                      }}
                    />
                    <span className="ap-vig" />
                  </div>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 7 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                      <span style={{ fontFamily: AP.mono, fontSize: 13, color: AP.ink }} title={j.asset_id}>
                        asset {shortId(j.asset_id)}
                      </span>
                      <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>
                        · attempt {j.attempt_count ?? 1}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.lumenSoft }}>
                        pipeline v{j.pipeline_version ?? '1'}
                      </span>
                      <Dot c={AP.lumen} size={6} glow />
                      <span className="ap-pulse-dot" style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>
                        inferring…
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* failed jobs + retry */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <Eyebrow c={STATUS.err.c}>Failed jobs</Eyebrow>
              <span style={{ fontFamily: AP.mono, fontSize: 11, color: AP.ink3 }}>
                {failed.length} total{failed.length > 8 ? ' · showing 8' : ''}
              </span>
              <span style={{ flex: 1 }} />
              {failed.length > 0 && <ActBtn onClick={retryAll}>⟳ Retry all failed</ActBtn>}
            </div>
            {failed.length === 0 ? (
              <span style={{ fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3 }}>No failures — all clear.</span>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {failed.slice(0, 8).map((j) => (
                  <div
                    key={j._id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 13,
                      padding: '10px 13px',
                      borderRadius: 11,
                      background: AP.card,
                      border: `1px solid ${AP.line2}`,
                    }}
                  >
                    <div className="ap-photo" style={{ width: 40, height: 40, borderRadius: 8, background: AP.cardHi, flex: '0 0 auto' }}>
                      <img
                        src={`${API}/images/${j.asset_id}/thumbnail`}
                        alt=""
                        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                      <span className="ap-vig" />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontFamily: AP.mono, fontSize: 12.5, color: AP.ink }} title={j.asset_id}>
                        asset {shortId(j.asset_id)} · attempt {j.attempt_count ?? 1}
                      </div>
                      <div
                        style={{
                          fontFamily: AP.sans,
                          fontSize: 11.5,
                          color: STATUS.err.c,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                        title={j.last_error?.message ?? ''}
                      >
                        {j.last_error?.message ?? j.last_error?.type ?? 'processing failed'}
                      </div>
                    </div>
                    <ActBtn onClick={() => retryJob(j._id)} disabled={retrying[j._id]}>
                      {retrying[j._id] ? '⟳ …' : '⟳ Retry'}
                    </ActBtn>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* activity feed */}
        <div
          style={{
            width: 392,
            flex: '0 0 auto',
            borderLeft: `1px solid ${AP.line}`,
            background: AP.panel,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 10,
              padding: '15px 18px',
              borderBottom: `1px solid ${AP.line}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Dot c={AP.lumen} size={7} glow={running} />
              <Eyebrow c={AP.lumenSoft}>Job activity</Eyebrow>
            </div>
            <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>refreshes 5s</span>
          </div>
          <div
            className="ap-scroll"
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: 'auto',
              padding: '12px 16px',
              background: AP.void,
              fontFamily: AP.mono,
              fontSize: 11.5,
              lineHeight: 1.9,
            }}
          >
            {feed.length === 0 && <span style={{ color: AP.ink4 }}>no job activity yet</span>}
            {feed.map((j) => (
              <div key={j._id} style={{ display: 'flex', gap: 10 }}>
                <span style={{ color: AP.ink4, flex: '0 0 auto' }}>
                  {j.updated_at ? new Date(j.updated_at).toLocaleTimeString() : '—'}
                </span>
                <span style={{ color: LOG_COLOR[j.status] ?? AP.ink3, flex: '0 0 auto', width: 76 }}>{j.status}</span>
                <span style={{ color: AP.ink2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  asset {shortId(j.asset_id)}
                </span>
              </div>
            ))}
            {running && (
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 2 }}>
                <span className="ap-pulse-dot" style={{ width: 7, height: 14, background: AP.lumen, borderRadius: 2 }} />
              </div>
            )}
          </div>
          <div style={{ padding: '11px 16px', borderTop: `1px solid ${AP.line}` }}>
            <span style={{ fontFamily: AP.sans, fontSize: 11, color: AP.ink4, lineHeight: 1.4 }}>
              ✦ True live log streaming needs a worker log channel — this feed is derived from job status updates.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
