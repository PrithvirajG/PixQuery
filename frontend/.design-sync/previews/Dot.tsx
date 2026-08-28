import React from 'react';
import { Dot, AP, STATUS } from 'pixquery-aperture';

const row: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 16,
  padding: 12,
  background: AP.base,
};

const label: React.CSSProperties = {
  fontFamily: AP.mono,
  fontSize: 11,
  color: AP.ink3,
};

// Default size, Lumen accent — the color used for "this is intelligence-driven".
export const Default = () => (
  <div style={row}>
    <Dot />
    <span style={label}>default</span>
  </div>
);

// The status palette this app actually cycles through: idle, running, ok, error.
export const StatusColors = () => (
  <div style={row}>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {(['idle', 'run', 'ok', 'err'] as const).map((key) => (
        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Dot c={STATUS[key].c} glow={key === 'run'} />
          <span style={label}>{key}</span>
        </div>
      ))}
    </div>
  </div>
);

// Sizes range from a tight inline marker to a header-level indicator.
export const Sizes = () => (
  <div style={row}>
    <Dot c={AP.lumen} size={5} />
    <Dot c={AP.lumen} size={7} />
    <Dot c={AP.lumen} size={10} />
    <Dot c={AP.lumen} size={14} />
  </div>
);

// `glow` adds a soft halo — used for "this is live right now" (a running job,
// a connected socket) rather than a static status.
export const GlowOnOff = () => (
  <div style={{ ...row, background: AP.panel }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Dot c={STATUS.ok.c} glow={false} />
      <span style={label}>connected (no glow)</span>
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Dot c={STATUS.ok.c} glow />
      <span style={label}>connected (glow)</span>
    </div>
  </div>
);
