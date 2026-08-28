import React from 'react';
import { Muted, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { width: 280, padding: 16, background: AP.base, display: 'flex', flexDirection: 'column', gap: 10 };

// Real empty/explanatory strings this app actually shows — not placeholder text.
export const RealMessages = () => (
  <div style={stage}>
    <Muted>No objects detected.</Muted>
    <Muted>Not processed yet — use Process to run this pipeline.</Muted>
    <Muted>This run failed — no outputs were produced.</Muted>
  </div>
);
