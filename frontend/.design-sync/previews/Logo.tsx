import React from 'react';
import { Logo, AP } from 'pixquery-aperture';

const dark: React.CSSProperties = { padding: 20, background: AP.base, display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'flex-start' };
const light: React.CSSProperties = { padding: 20, background: '#F7F8FC', display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'flex-start' };

// The default lockup — mark beside the wordmark, on the dark canvas every
// other Aperture component assumes.
export const Horizontal = () => (
  <div style={dark}>
    <Logo size={40} />
  </div>
);

// Mark above wordmark — narrower footprint for a splash/loading state or a
// vertical sidebar.
export const Stacked = () => (
  <div style={dark}>
    <Logo variant="stacked" size={56} />
  </div>
);

// Icon only — nav rails, favicons, app-icon tiles. No wordmark at any size.
export const MarkOnly = () => (
  <div style={{ ...dark, flexDirection: 'row', gap: 20, alignItems: 'center' }}>
    <Logo variant="mark" size={40} />
    <Logo variant="mark" size={26} />
    <Logo variant="mark" size={16} />
  </div>
);

// `theme="light"`: the wordmark switches to dark ink for a light background;
// the mark's own gradient is unaffected by theme.
export const LightBackground = () => (
  <div style={light}>
    <Logo theme="light" size={40} />
  </div>
);

// `theme="mono"`: everything — mark and wordmark alike — inherits
// `currentColor`, for single-colour contexts like a solid-fill app tile.
export const MonoOnColor = () => (
  <div style={{ ...dark, background: 'linear-gradient(150deg,#8B5CF6 0%,#5b3fd6 100%)', color: '#fff' }}>
    <Logo theme="mono" size={40} />
  </div>
);

// In place, at the size the nav rail and the loading screen actually use.
export const InNavRail = () => (
  <div style={{ padding: 18, background: AP.panel, borderRight: `1px solid ${AP.line}`, display: 'inline-flex' }}>
    <Logo variant="mark" size={26} />
  </div>
);
