import React from 'react';
import { DeleteOutputsBtn, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { padding: 16, background: AP.base, display: 'flex', alignItems: 'center', gap: 16 };
const label: React.CSSProperties = { fontFamily: AP.mono, fontSize: 11, color: AP.ink3 };

// Has stored outputs to delete — enabled.
export const Enabled = () => (
  <div style={row}>
    <DeleteOutputsBtn onClick={() => {}} />
    <span style={label}>has outputs</span>
  </div>
);

// Nothing stored for this pipeline yet — disabled, nothing to delete.
export const Disabled = () => (
  <div style={row}>
    <DeleteOutputsBtn onClick={() => {}} disabled />
    <span style={label}>no outputs</span>
  </div>
);

// A delete request is in flight.
export const Busy = () => (
  <div style={row}>
    <DeleteOutputsBtn onClick={() => {}} busy />
    <span style={label}>deleting…</span>
  </div>
);
