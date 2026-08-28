import React from 'react';
import { MetricRing, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 20, padding: 16, background: AP.base, alignItems: 'center' };

// Workspace coverage ring with its label, plus the plain unlabeled variant.
export const Labeled = () => (
  <div style={row}>
    <MetricRing v={0.68} label="done" />
    <MetricRing v={0.32} label="left" />
  </div>
);

// Larger size, for a dashboard-level summary stat rather than an inline chip.
export const LargeUnlabeled = () => (
  <div style={row}>
    <MetricRing v={0.91} size={80} />
  </div>
);
