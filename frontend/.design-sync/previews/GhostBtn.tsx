import React from 'react';
import { GhostBtn, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'inline-flex', gap: 10 };

// The default, low-emphasis action button — used for "Open", "Copy id" etc.
export const Default = () => (
  <div style={stage}>
    <GhostBtn onClick={() => {}}>↗ Open</GhostBtn>
  </div>
);

// Several ghost buttons side by side, as they appear in a toolbar row.
export const Toolbar = () => (
  <div style={stage}>
    <GhostBtn onClick={() => {}}>↗ Open</GhostBtn>
    <GhostBtn onClick={() => {}}>⧉ Copy id</GhostBtn>
    <GhostBtn onClick={() => {}}>🗑 Clear outputs</GhostBtn>
  </div>
);

// Disabled — dimmed, cursor becomes not-allowed.
export const Disabled = () => (
  <div style={stage}>
    <GhostBtn disabled title="Needs a similar-image endpoint on the backend — not available yet">
      ✦ Find similar
    </GhostBtn>
  </div>
);
