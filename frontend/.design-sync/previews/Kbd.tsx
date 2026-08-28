import React from 'react';
import { Kbd, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'flex', alignItems: 'center', gap: 10 };

// The two shortcuts actually surfaced in the app: opening search, and
// dismissing a modal/drawer.
export const Default = () => (
  <div style={stage}>
    <Kbd>⌘K</Kbd>
    <Kbd>Esc</Kbd>
  </div>
);

// Paired with plain text, as it appears inline in a hint row.
export const InlineHint = () => (
  <div style={{ ...stage, fontFamily: AP.sans, fontSize: 12.5, color: AP.ink3 }}>
    <span>Press</span>
    <Kbd>⌘K</Kbd>
    <span>to search</span>
  </div>
);
