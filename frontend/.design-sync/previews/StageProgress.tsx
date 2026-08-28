import React from 'react';
import { StageProgress, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { display: 'flex', gap: 16, padding: 16, background: AP.panel, alignItems: 'center' };
const caption: React.CSSProperties = { fontFamily: AP.sans, fontSize: 11, color: AP.ink3 };

// Live progress within a single pipeline run — "stage 2/3 · captioning".
export const MidRun = () => (
  <div style={row}>
    <StageProgress stage={{ index: 2, total: 3, node_type: 'captioning' }} />
  </div>
);

// The first stage of a longer run.
export const FirstStage = () => (
  <div style={row}>
    <StageProgress stage={{ index: 1, total: 5, node_type: 'object_detection' }} />
  </div>
);

// `stage` is null/undefined whenever nothing is running — the component
// renders nothing at all then. Shown here labeled rather than as a bare
// component alone, since an unlabeled empty render is indistinguishable from
// a broken one in a screenshot.
export const Idle = () => (
  <div style={row}>
    <span style={caption}>StageProgress with no active stage renders nothing:</span>
    <StageProgress stage={null} />
    <span style={caption}>(nothing after the colon is correct, not a bug)</span>
  </div>
);
