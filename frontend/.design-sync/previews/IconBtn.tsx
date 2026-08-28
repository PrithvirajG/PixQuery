import React from 'react';
import { IconBtn, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'inline-flex', gap: 10 };

// A square icon-only button — nav rail toggles, view switches.
export const Default = () => (
  <div style={stage}>
    <IconBtn title="Grid view" onClick={() => {}}>▦</IconBtn>
  </div>
);

// `active` marks the current selection among a set of IconBtns (e.g. the
// active view in a toggle group) with the Lumen accent.
export const ActiveGroup = () => (
  <div style={stage}>
    <IconBtn title="Grid view" active onClick={() => {}}>▦</IconBtn>
    <IconBtn title="List view" onClick={() => {}}>☰</IconBtn>
  </div>
);
