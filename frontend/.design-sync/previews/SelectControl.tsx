import React from 'react';
import { SelectControl, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 10, padding: 16, background: AP.base };

// Default (inactive) header control — a sort/group dropdown trigger.
export const Default = () => (
  <div style={row}>
    <SelectControl label="sort" value="newest" onClick={() => {}} />
  </div>
);

// Active — the control is currently expanded/focused.
export const Active = () => (
  <div style={row}>
    <SelectControl label="group by" value="pipeline" active onClick={() => {}} />
  </div>
);

// Accent — marks a non-default selection worth calling out (e.g. a filter
// that's actively narrowing results), with the ✦ marker.
export const Accent = () => (
  <div style={row}>
    <SelectControl label="filter" value="faces only" accent onClick={() => {}} />
  </div>
);
