import React from 'react';
import { Chip, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'flex-start' };

// The default carried style — a match-reason pill with a score.
export const Pill = () => (
  <div style={stage}>
    <Chip reason="matches “golden retriever on a dock”" score={0.92} />
    <Chip reason="no score" />
  </div>
);

// The badge variant — sits over a photo thumbnail, so it gets a translucent
// backdrop-blur background instead of a solid one.
export const Badge = () => (
  <div style={{ ...stage, background: AP.cardHi }}>
    <Chip reason="sunset over water" score="0.88" variant="badge" />
  </div>
);

// The underline variant — a Lumen-gradient underline instead of a filled pill,
// for a lighter-weight inline mention.
export const Underline = () => (
  <div style={stage}>
    <Chip reason="outdoor scene" score={0.81} variant="underline" />
  </div>
);

// `size="sm"` shrinks the type scale for denser layouts (e.g. a search result grid).
export const SmallSize = () => (
  <div style={stage}>
    <Chip reason="tighter row" score={0.76} size="sm" />
  </div>
);
