import React, { useState } from 'react';
import { EyeBtn, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'inline-flex', gap: 10, alignItems: 'center' };

// Shows/hides something on the page — a pipeline's outputs, one stage's body
// — without persisting a setting. `on` is what's currently visible, not a
// saved value, which is why this is an eye and not a switch.
export const Shown = () => (
  <div style={stage}>
    <EyeBtn on onClick={() => {}} />
  </div>
);

export const Hidden = () => (
  <div style={stage}>
    <EyeBtn on={false} onClick={() => {}} />
  </div>
);

// Interactive: click to see the icon and tint swap, and the default title
// track the state without the caller writing either by hand.
export const Interactive = () => {
  const [on, setOn] = useState(true);
  return (
    <div style={stage}>
      <EyeBtn on={on} onClick={() => setOn((v) => !v)} />
    </div>
  );
};

// `size` follows the same scale as IconBtn — 27 for a header control
// cluster (PipelineSection), 20 for a per-row inline control (StageCard).
export const Sizes = () => (
  <div style={stage}>
    <EyeBtn on onClick={() => {}} size={27} />
    <EyeBtn on onClick={() => {}} size={20} />
  </div>
);
