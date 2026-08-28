import React from 'react';
import { HealthPill, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 10, padding: 16, background: AP.base, flexWrap: 'wrap' };

// The full status sweep this app actually cycles a pipeline/job through.
export const StatesSweep = () => (
  <div style={row}>
    <HealthPill state="idle" label="Idle" />
    <HealthPill state="queue" label="Queued" />
    <HealthPill state="run" label="Running" />
    <HealthPill state="ok" label="Completed" />
    <HealthPill state="warn" label="Retrying" />
    <HealthPill state="err" label="Failed" />
  </div>
);

// `sm` is the compact variant used inline in dense rows (a jobs table cell)
// rather than as a standalone status chip.
export const CompactSize = () => (
  <div style={row}>
    <HealthPill state="ok" label="Completed" sm />
    <HealthPill state="err" label="Failed" sm />
    <HealthPill state="run" label="Running" sm />
  </div>
);
