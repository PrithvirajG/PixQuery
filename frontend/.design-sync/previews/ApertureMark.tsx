import React from 'react';
import { ApertureMark, AP } from 'pixquery-aperture';

const row: React.CSSProperties = {
  display: 'flex',
  gap: 16,
  alignItems: 'center',
  padding: 16,
  background: AP.base,
};

// The brand mark at its real nav-rail size, next to a larger copy so the
// concentric ring + glow reads clearly at review-thumbnail scale.
export const Default = () => (
  <div style={row}>
    <ApertureMark />
    <ApertureMark size={48} />
    <ApertureMark size={80} />
  </div>
);
