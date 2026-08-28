import React from 'react';
import { MagIcon, AP } from 'pixquery-aperture';

const row: React.CSSProperties = {
  display: 'flex',
  gap: 16,
  alignItems: 'center',
  padding: 16,
  background: AP.panel,
};

// Default color (AP.ink3) at the real-world search-bar size, next to a larger
// copy so the glass + handle shape is actually legible in a review thumbnail.
export const Default = () => (
  <div style={row}>
    <MagIcon />
    <MagIcon size={48} />
  </div>
);

// The two colors it's actually shown in: muted (idle placeholder text) and
// full ink (an active/focused search field).
export const Colors = () => (
  <div style={row}>
    <MagIcon size={32} c={AP.ink3} />
    <MagIcon size={32} c={AP.ink} />
    <MagIcon size={32} c={AP.lumen} />
  </div>
);
