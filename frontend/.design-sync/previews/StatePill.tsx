import React from 'react';
import { StatePill, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 10, padding: 16, background: AP.panel, flexWrap: 'wrap', alignItems: 'center' };

// The full (image, pipeline) lifecycle this pill mirrors — same five states
// PipelineSection derives from the backend's job status.
export const AllStates = () => (
  <div style={row}>
    <StatePill state="not_started" />
    <StatePill state="queued" />
    <StatePill state="processing" />
    <StatePill state="completed" />
    <StatePill state="failed" />
  </div>
);
