import React from 'react';
import { Photo, AP } from 'pixquery-aperture';

// `.ap-photo` is position:relative/overflow:hidden with absolutely-positioned
// children (image, grain vignette, badge) — real usage always sizes it via a
// parent grid cell, so the preview must give it an explicit box or its
// content has nothing to lay out against.
const box: React.CSSProperties = { width: 220, height: 160 };
const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'flex', gap: 16 };

const badge = (
  <span
    style={{
      fontFamily: AP.mono,
      fontSize: 10,
      fontWeight: 600,
      color: '#fff',
      background: AP.lumenGrad,
      borderRadius: 6,
      padding: '2px 7px',
      boxShadow: '0 2px 8px rgba(99,102,241,.5)',
    }}
  >
    NEW
  </span>
);

// No image loaded (a thumbnail request pending, or none available) — grain +
// vignette chrome still shows, on the raised card background.
export const Empty = () => (
  <div style={stage}>
    <Photo style={box} />
  </div>
);

// With a corner badge — the pattern used to flag a result on top of its
// thumbnail (e.g. a match indicator).
export const WithBadge = () => (
  <div style={stage}>
    <Photo style={box} badge={badge} />
  </div>
);
