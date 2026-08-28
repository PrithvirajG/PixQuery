import React from 'react';
import { ControlHeader, GhostBtn, LumenBtn, AP } from 'pixquery-aperture';

// Full-width bar by design (flex row, space-between) — needs a wide stage or
// it reads as squeezed. 640px mirrors the Control Room pages it heads.
const stage: React.CSSProperties = { width: 640, background: AP.base };

export const Default = () => (
  <div style={stage}>
    <ControlHeader
      breadcrumb="Pipelines"
      title="Object Detection"
      count={12}
      actions={
        <>
          <GhostBtn>↻ Rescan</GhostBtn>
          <LumenBtn>+ New pipeline</LumenBtn>
        </>
      }
    />
  </div>
);

// No trailing count and a single action — the sparser end of the range.
export const NoCount = () => (
  <div style={stage}>
    <ControlHeader breadcrumb="Workspaces" title="Personal Photos" actions={<GhostBtn>⚙ Settings</GhostBtn>} />
  </div>
);
