import React from 'react';
import { Counter, AP, STATUS } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 12, padding: 16, background: AP.base };

// A row of stat cards — how PipelineStatsView shows workspace-wide counters.
export const Row = () => (
  <div style={row}>
    <Counter label="total jobs" value="412" />
    <Counter label="completed" value="398" c={STATUS.ok.c} sub="96.6%" />
    <Counter label="failed" value="14" c={STATUS.err.c} accent={{ c: STATUS.err.c, line: STATUS.err.line }} />
  </div>
);

// `accent` is a {c, line} pair (not a boolean) — it recolors the eyebrow label
// and the card's own border to match, for the one counter that needs to stand out.
export const Accented = () => (
  <div style={row}>
    <Counter label="queued now" value="3" accent={{ c: AP.lumenSoft, line: AP.lumenLine }} sub="live" />
  </div>
);
