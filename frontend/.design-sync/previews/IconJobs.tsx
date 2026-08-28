import React from 'react';
import { IconJobs, AP } from 'pixquery-aperture';

const row: React.CSSProperties = {
  display: 'flex',
  gap: 16,
  alignItems: 'center',
  padding: 16,
  background: AP.panel,
};

export const Default = () => (
  <div style={row}>
    <IconJobs c={AP.ink} />
    <IconJobs s={48} c={AP.ink} />
  </div>
);

export const ActiveVsInactive = () => (
  <div style={row}>
    <IconJobs s={28} c={AP.ink3} />
    <IconJobs s={28} c={AP.lumen} />
  </div>
);
