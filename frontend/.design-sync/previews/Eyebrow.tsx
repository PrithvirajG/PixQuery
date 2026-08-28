import React from 'react';
import { Eyebrow, AP, STATUS } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'flex', flexDirection: 'column', gap: 10 };

// Default: the faint mono section label used above almost every panel.
export const Default = () => (
  <div style={stage}>
    <Eyebrow>File info · always shown</Eyebrow>
  </div>
);

// A custom color ties the label to an accent (Lumen for AI-driven sections,
// a status color for a health-adjacent one).
export const AccentColors = () => (
  <div style={stage}>
    <Eyebrow c={AP.lumenSoft}>Pipeline outputs</Eyebrow>
    <Eyebrow c={STATUS.err.c}>Failed jobs</Eyebrow>
  </div>
);
