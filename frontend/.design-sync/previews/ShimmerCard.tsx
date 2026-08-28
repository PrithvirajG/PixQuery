import React from 'react';
import { ShimmerCard, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 12, padding: 16, background: AP.base, width: 320 };

// Default 3-line placeholder — stands in for one pipeline output card while
// its pipeline is queued or processing (ImageDetails swaps real OutputCards
// for a stack of these mid-run).
export const Default = () => (
  <div style={row}>
    <ShimmerCard label="Detections is processing — waiting for results" />
  </div>
);

// Fewer lines, for a shorter expected output (a caption, not a detections list).
export const ShortForm = () => (
  <div style={row}>
    <ShimmerCard lines={1} label="Caption is queued" />
  </div>
);
