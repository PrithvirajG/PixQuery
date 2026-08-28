import React, { useState } from 'react';
import { Toggle, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'inline-flex', gap: 16, alignItems: 'center' };
const label: React.CSSProperties = { fontFamily: AP.mono, fontSize: 11, color: AP.ink3 };

// Interactive — click to flip. Used to show/hide a pipeline's outputs.
export const Interactive = () => {
  const [on, setOn] = useState(true);
  return (
    <div style={stage}>
      <Toggle on={on} onClick={() => setOn((v) => !v)} title="Show outputs" />
      <span style={label}>{on ? 'on' : 'off'}</span>
    </div>
  );
};

// Both static states side by side, for a direct visual comparison.
export const OnAndOff = () => (
  <div style={stage}>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
      <Toggle on onClick={() => {}} />
      <span style={label}>on</span>
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
      <Toggle on={false} onClick={() => {}} />
      <span style={label}>off</span>
    </div>
  </div>
);
