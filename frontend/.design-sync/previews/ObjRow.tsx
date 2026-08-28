import React, { useState } from 'react';
import { ObjRow, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { width: 260, padding: 16, background: AP.base, display: 'flex', flexDirection: 'column', gap: 4 };

// No `onToggle`: the static marker variant — used for classification labels,
// which aren't individually hideable (only detections are). Each label gets
// its own deterministic colour (see `objColor`), which is why "outdoor" and
// "daytime" render as different hues rather than both a single accent colour.
export const StaticMarker = () => (
  <div style={stage}>
    <ObjRow name="outdoor" n={1} c={0.94} task="resnet" />
    <ObjRow name="daytime" n={1} c={0.81} task="resnet" />
  </div>
);

// With `onToggle`: a real checkbox that hides that label's boxes on the bbox
// overlay elsewhere on the page. `n` shows a repeat count when >1. The
// checkbox's own accent colour is the object's colour, not a fixed one.
export const CheckboxInteractive = () => {
  const [checked, setChecked] = useState(true);
  return (
    <div style={stage}>
      <ObjRow name="car" n={2} c={0.89} task="yolo" checked={checked} onToggle={() => setChecked((v) => !v)} />
    </div>
  );
};

// Toggled off: the whole row dims and the label strikes through, so a hidden
// box reads as hidden in the list too — not just a greyed-out checkbox.
export const ToggledOff = () => (
  <div style={stage}>
    <ObjRow name="bicycle" n={1} c={0.72} task="yolo" checked={false} onToggle={() => {}} />
  </div>
);

// `highlighted` — driven by hovering the row — tints the background with the
// row's own colour at low opacity, the same colour its box uses on the image
// overlay, so the two visibly agree without hovering the box itself.
export const Highlighted = () => (
  <div style={stage}>
    <ObjRow name="person" n={1} c={0.85} task="yolo" highlighted onHoverEnter={() => {}} onHoverLeave={() => {}} />
    <ObjRow name="motorcycle" n={1} c={0.47} task="yolo" onHoverEnter={() => {}} onHoverLeave={() => {}} />
  </div>
);

// Same label, two different producing models (`task`) — coloured differently
// on purpose. Without namespacing by task, both "person" rows would collide
// on one colour even though they come from unrelated detectors.
export const SameLabelDifferentTask = () => (
  <div style={stage}>
    <ObjRow name="person" n={1} c={0.85} task="yolo" />
    <ObjRow name="person" n={1} c={0.62} task="opencv_haar" />
  </div>
);

// A low-confidence detection — the meter should read visibly emptier.
export const LowConfidence = () => (
  <div style={stage}>
    <ObjRow name="motorcycle" n={1} c={0.24} task="yolo" />
  </div>
);
