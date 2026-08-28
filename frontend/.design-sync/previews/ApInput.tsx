import React, { useState } from 'react';
import { ApInput, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, maxWidth: 320, display: 'flex', flexDirection: 'column', gap: 12 };

// A controlled text field, as used for search/filter inputs in the app.
export const Text = () => {
  const [v, setV] = useState('street photography');
  return (
    <div style={stage}>
      <ApInput placeholder="Search images…" value={v} onChange={(e) => setV(e.target.value)} />
    </div>
  );
};

export const Empty = () => (
  <div style={stage}>
    <ApInput placeholder="Workspace name" />
  </div>
);

export const Password = () => (
  <div style={stage}>
    <ApInput type="password" value="hunter2" onChange={() => {}} />
  </div>
);

export const Disabled = () => (
  <div style={stage}>
    <ApInput value="Read-only path" disabled onChange={() => {}} />
  </div>
);
