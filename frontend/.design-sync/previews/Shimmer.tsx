import React from 'react';
import { Shimmer, AP } from 'pixquery-aperture';

const stack: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 10, padding: 16, background: AP.base, width: 220 };

// A single loading line — the animation is a moving gradient (`ap-shimmer`),
// so a still capture shows one frame of the sheen rather than motion; that's
// expected, not a rendering defect.
export const SingleLine = () => (
  <div style={stack}>
    <Shimmer />
  </div>
);

// The shapes it actually stands in for: a short label-width bar and a
// paragraph-width bar, matching how ShimmerCard composes it.
export const Sizes = () => (
  <div style={stack}>
    <Shimmer w={82} h={11} />
    <Shimmer w="100%" h={10} />
    <Shimmer w="58%" h={10} />
  </div>
);
