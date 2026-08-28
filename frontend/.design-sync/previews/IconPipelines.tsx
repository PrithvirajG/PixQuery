import React from 'react';
import { IconPipelines, AP } from 'pixquery-aperture';

const row: React.CSSProperties = {
  display: 'flex',
  gap: 16,
  alignItems: 'center',
  padding: 16,
  background: AP.panel,
};

export const Default = () => (
  <div style={row}>
    <IconPipelines c={AP.ink} />
    <IconPipelines s={48} c={AP.ink} />
  </div>
);

export const ActiveVsInactive = () => (
  <div style={row}>
    <IconPipelines s={28} c={AP.ink3} />
    <IconPipelines s={28} c={AP.lumen} />
  </div>
);
