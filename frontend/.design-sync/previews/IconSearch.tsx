import React from 'react';
import { IconSearch, AP } from 'pixquery-aperture';

const row: React.CSSProperties = {
  display: 'flex',
  gap: 16,
  alignItems: 'center',
  padding: 16,
  background: AP.panel,
};

// `c` has no default — every real usage must pass one, so this preview always
// does too. Real size (20px) plus a larger copy for legibility.
export const Default = () => (
  <div style={row}>
    <IconSearch c={AP.ink} />
    <IconSearch s={48} c={AP.ink} />
  </div>
);

// The nav rail's two states: inactive (ink3) vs the active/selected item (lumen).
export const ActiveVsInactive = () => (
  <div style={row}>
    <IconSearch s={28} c={AP.ink3} />
    <IconSearch s={28} c={AP.lumen} />
  </div>
);
