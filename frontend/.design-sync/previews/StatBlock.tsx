import React from 'react';
import { StatBlock, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 28, padding: 16, background: AP.base };

export const Default = () => (
  <div style={row}>
    <StatBlock label="images" value="1,204" />
  </div>
);

// `sub` adds a secondary mono line beneath the value (a trend, a unit, a date).
export const WithSub = () => (
  <div style={row}>
    <StatBlock label="matches" value="38" sub="top score 0.94" />
  </div>
);

// `accent` shifts the value into the Lumen accent color — used to draw the
// eye to the one stat that matters most in a row of several.
export const Accent = () => (
  <div style={row}>
    <StatBlock label="images" value="1,204" />
    <StatBlock label="processed" value="1,198" sub="99.5%" accent />
    <StatBlock label="failed" value="6" />
  </div>
);
