import React from 'react';
import { IconWorkspaces, AP } from 'pixquery-aperture';

const row: React.CSSProperties = {
  display: 'flex',
  gap: 16,
  alignItems: 'center',
  padding: 16,
  background: AP.panel,
};

export const Default = () => (
  <div style={row}>
    <IconWorkspaces c={AP.ink} />
    <IconWorkspaces s={48} c={AP.ink} />
  </div>
);

export const ActiveVsInactive = () => (
  <div style={row}>
    <IconWorkspaces s={28} c={AP.ink3} />
    <IconWorkspaces s={28} c={AP.lumen} />
  </div>
);
