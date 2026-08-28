import React from 'react';
import { Bar, AP, STATUS } from 'pixquery-aperture';

const stack: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 14, padding: 16, background: AP.base, width: 220 };
const label: React.CSSProperties = { fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3, marginBottom: 5 };

// A finished pipeline's coverage bar — the default Lumen gradient fill.
export const Progress = () => (
  <div style={stack}>
    <div>
      <div style={label}>72% processed</div>
      <Bar v={0.72} />
    </div>
  </div>
);

// `pulse` adds a moving sheen — used while a job is actively running, not
// just "partially done".
export const LivePulsing = () => (
  <div style={stack}>
    <div>
      <div style={label}>running…</div>
      <Bar v={0.35} pulse />
    </div>
  </div>
);

// Custom color + thickness, and the empty/full extremes.
export const ColorAndExtremes = () => (
  <div style={stack}>
    <div>
      <div style={label}>error rate</div>
      <Bar v={0.18} c={STATUS.err.c} h={7} />
    </div>
    <div>
      <div style={label}>0%</div>
      <Bar v={0} />
    </div>
    <div>
      <div style={label}>100%</div>
      <Bar v={1} c={STATUS.ok.c} />
    </div>
  </div>
);
