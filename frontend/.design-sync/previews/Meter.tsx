import React from 'react';
import { Meter, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-start' };

// The confidence axis this component exists to show — low, mid, high, and
// near-certain — the bar fill and the printed number both track `v`.
export const ConfidenceRange = () => (
  <div style={stage}>
    <Meter v={0.24} />
    <Meter v={0.58} />
    <Meter v={0.85} />
    <Meter v={0.99} />
  </div>
);
