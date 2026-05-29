import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';

const STATUS_STYLES = {
  queued:     'text-slate-300 bg-slate-800/60 border-slate-700/50',
  processing: 'text-violet-300 bg-violet-900/40 border-violet-700/50',
  completed:  'text-green-300 bg-green-900/30 border-green-700/50',
  failed:     'text-red-300 bg-red-900/30 border-red-700/50',
};

const STATUS_DOTS = {
  queued:     'bg-slate-400',
  processing: 'bg-violet-400 animate-pulse',
  completed:  'bg-green-400',
  failed:     'bg-red-400',
};

/* ── Stat Card ──────────────────────────────────────────────────── */
function StatCard({ label, value, icon, iconBg, valueColor, sub }) {
  return (
    <div className="flex flex-col justify-between gap-3 p-4 bg-slate-900/60 border border-slate-800
                    rounded-2xl backdrop-blur hover:border-slate-700 transition-all min-h-[108px]">
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider leading-tight">
          {label}
        </span>
        <div className={`shrink-0 w-8 h-8 rounded-xl flex items-center justify-center ${iconBg}`}>
          {icon}
        </div>
      </div>
      <div>
        <p className={`text-3xl font-extrabold tabular-nums ${valueColor}`}>
          {value ?? '—'}
        </p>
        {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

/* ── Jobs Table ─────────────────────────────────────────────────── */
function JobsTable({ jobs, onRequeue }) {
  const [sortField, setSortField] = useState('updated_at');
  const [sortDir, setSortDir]     = useState('desc');

  const toggleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const sorted = [...jobs].sort((a, b) => {
    const av = a[sortField] ?? '', bv = b[sortField] ?? '';
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const SortIcon = ({ field }) => (
    <svg
      className={`w-3 h-3 inline ml-1 ${sortField === field ? 'text-violet-400' : 'text-slate-700'}`}
      fill="none" viewBox="0 0 24 24" stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d={sortField === field && sortDir === 'asc' ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} />
    </svg>
  );

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center
                      border border-slate-800 rounded-2xl bg-slate-900/30">
        <svg className="w-10 h-10 text-slate-700 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2
                   M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <p className="text-sm text-slate-500">No jobs yet</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-900/80">
            {[
              ['asset_id', 'Asset'],
              ['pipeline_id', 'Pipeline'],
              ['status', 'Status'],
              ['updated_at', 'Updated'],
            ].map(([field, label]) => (
              <th
                key={field}
                className="text-left px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wider"
              >
                <button
                  onClick={() => toggleSort(field)}
                  className="hover:text-slate-300 transition-colors flex items-center gap-0.5"
                >
                  {label}
                  <SortIcon field={field} />
                </button>
              </th>
            ))}
            <th className="text-left px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Attempts
            </th>
            <th className="px-4 py-3 w-24" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80">
          {sorted.map(job => (
            <tr key={job._id} className="hover:bg-slate-800/25 transition-colors group">
              <td className="px-4 py-3">
                <span className="text-[11px] font-mono text-slate-400">
                  {job.asset_id?.slice(0, 10) ?? '—'}…
                </span>
              </td>
              <td className="px-4 py-3 max-w-[140px]">
                <span className="text-[11px] text-slate-400 truncate block">{job.pipeline_id ?? '—'}</span>
              </td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center gap-1.5 text-[11px] font-semibold
                                  px-2.5 py-1 rounded-full border ${STATUS_STYLES[job.status] ?? STATUS_STYLES.queued}`}>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOTS[job.status] ?? 'bg-slate-500'}`} />
                  {job.status}
                </span>
              </td>
              <td className="px-4 py-3 text-[11px] text-slate-500 whitespace-nowrap">
                {job.updated_at ? new Date(job.updated_at).toLocaleString() : '—'}
              </td>
              <td className="px-4 py-3 text-[11px] text-slate-500 text-center">
                {job.attempt_count ?? 0}
              </td>
              <td className="px-4 py-3">
                {job.status === 'failed' && (
                  <button
                    onClick={() => onRequeue(job._id)}
                    className="opacity-0 group-hover:opacity-100 flex items-center gap-1.5
                               px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700
                               text-[11px] font-semibold text-slate-400
                               hover:text-violet-400 hover:border-violet-700/50 transition-all"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581
                               m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Requeue
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Main View ──────────────────────────────────────────────────── */
function ProgressTrackingView() {
  const [overview, setOverview]   = useState(null);
  const [jobs, setJobs]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [jobLimit, setJobLimit]   = useState(50);
  const [refreshing, setRefresh]  = useState(false);

  const loadData = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefresh(true);
    else setLoading(true);
    try {
      const [ovRes, jobsRes] = await Promise.all([
        axios.get(`${API}/stats/overview`),
        axios.get(`${API}/stats/jobs/recent?limit=${jobLimit}`),
      ]);
      setOverview(ovRes.data);
      setJobs(jobsRes.data);
      setError('');
    } catch {
      setError('Failed to load statistics');
    } finally {
      setLoading(false);
      setRefresh(false);
    }
  }, [jobLimit]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'processing' || j.status === 'queued');
    if (!hasActive) return;
    const id = setInterval(() => loadData(true), 15000);
    return () => clearInterval(id);
  }, [jobs, loadData]);

  const handleRequeue = async (jobId) => {
    try {
      await axios.post(`${API}/jobs/${jobId}/requeue`);
      await loadData(true);
    } catch {
      setError('Requeue failed');
    }
  };

  const STAT_CARDS = overview ? [
    {
      label: 'Total Images',
      value: overview.total_images?.toLocaleString(),
      iconBg: 'bg-violet-900/40',
      valueColor: 'text-violet-300',
      icon: <svg className="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>,
    },
    {
      label: 'Active Workspaces',
      value: overview.active_workspaces,
      iconBg: 'bg-teal-900/40',
      valueColor: 'text-teal-300',
      icon: <svg className="w-4 h-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>,
    },
    {
      label: 'Pipelines',
      value: overview.pipelines_defined,
      iconBg: 'bg-indigo-900/40',
      valueColor: 'text-indigo-300',
      icon: <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>,
    },
    {
      label: 'Jobs Completed',
      value: overview.jobs_completed?.toLocaleString(),
      iconBg: 'bg-green-900/40',
      valueColor: 'text-green-300',
      icon: <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>,
    },
    {
      label: 'Jobs Failed',
      value: overview.jobs_failed,
      iconBg: 'bg-red-900/40',
      valueColor: 'text-red-300',
      icon: <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>,
    },
    {
      label: 'Processing Now',
      value: overview.jobs_processing,
      iconBg: 'bg-amber-900/40',
      valueColor: 'text-amber-300',
      sub: overview.jobs_queued > 0 ? `${overview.jobs_queued} queued` : null,
      icon: <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>,
    },
  ] : [];

  return (
    <div className="flex flex-col gap-7 pb-10">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Jobs</h2>
          <p className="text-sm text-slate-500 mt-0.5">System overview and recent processing jobs</p>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800/60 border border-slate-700
                     text-sm font-semibold text-slate-400 hover:text-slate-200 hover:border-slate-600
                     disabled:opacity-50 transition-all"
        >
          <svg className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581
                     m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-xl px-4 py-3 text-sm text-red-400
                        flex items-center justify-between gap-3">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-700 hover:text-red-500">✕</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {/* Stat Cards — 2 cols mobile, 3 cols tablet, 6 cols desktop */}
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
            {STAT_CARDS.map(card => (
              <StatCard key={card.label} {...card} />
            ))}
          </div>

          {/* Recent Jobs */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-300">Recent Jobs</h3>
              <div className="flex items-center gap-3">
                <select
                  value={jobLimit}
                  onChange={e => setJobLimit(Number(e.target.value))}
                  className="bg-slate-800/60 border border-slate-700/60 rounded-xl px-3 py-2
                             text-xs text-slate-300 outline-none focus:border-violet-500/50 transition-all"
                >
                  {[20, 50, 100, 200].map(n => (
                    <option key={n} value={n}>Last {n}</option>
                  ))}
                </select>
                <span className="text-xs text-slate-600">{jobs.length} shown</span>
              </div>
            </div>
            <JobsTable jobs={jobs} onRequeue={handleRequeue} />
          </div>
        </>
      )}
    </div>
  );
}

export default ProgressTrackingView;
