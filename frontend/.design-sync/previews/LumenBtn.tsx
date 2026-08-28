import React from 'react';
import { LumenBtn, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'inline-flex', gap: 10 };

// The high-emphasis primary action — Lumen gradient fill, used for the one
// thing on a screen the user is most likely to want (e.g. "Find similar").
export const Default = () => (
  <div style={stage}>
    <LumenBtn onClick={() => {}}>✦ Find similar</LumenBtn>
  </div>
);

// Disabled — the gradient dims rather than disappearing, so it still reads as
// "the primary action" even while unavailable.
export const Disabled = () => (
  <div style={stage}>
    <LumenBtn disabled>✦ Find similar</LumenBtn>
  </div>
);
