import React from 'react';
import { IconBtn, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'inline-flex', gap: 10, alignItems: 'center' };

// Plain stroke SVGs, not text glyphs — renders identically everywhere,
// matching how real call sites pass IconBtn its icon (see PipelineSection's
// eye/reprocess/delete cluster in blocks.jsx).
const Grid = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="3" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="2" />
    <rect x="14" y="3" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="2" />
    <rect x="3" y="14" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="2" />
    <rect x="14" y="14" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="2" />
  </svg>
);
const List = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);
const Trash = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M4.5 7h15M9.5 4.5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <path d="M6.6 7.5l.8 11a1.6 1.6 0 0 0 1.6 1.5h6a1.6 1.6 0 0 0 1.6-1.5l.8-11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const Refresh = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M20 12a8 8 0 1 1-2.6-5.9" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />
    <path d="M20 3.6V7.4h-3.8" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// A square icon-only button — nav rail toggles, view switches.
export const Default = () => (
  <div style={stage}>
    <IconBtn title="Grid view" onClick={() => {}}><Grid /></IconBtn>
  </div>
);

// `active` marks the current selection among a set of IconBtns (e.g. the
// active view in a toggle group) with the Lumen accent.
export const ActiveGroup = () => (
  <div style={stage}>
    <IconBtn title="Grid view" active onClick={() => {}}><Grid /></IconBtn>
    <IconBtn title="List view" onClick={() => {}}><List /></IconBtn>
  </div>
);

// `tone="danger"` for a destructive action in an icon-only cluster — the
// sibling of ActBtn's danger tone for icon-only controls.
export const Danger = () => (
  <div style={stage}>
    <IconBtn title="Delete" tone="danger" onClick={() => {}}><Trash /></IconBtn>
  </div>
);

// `size` scales the square hit target for smaller contexts (a header
// cluster, a per-row inline control) without the icon looking shrunk.
export const Sizes = () => (
  <div style={stage}>
    <IconBtn title="34px (default)" onClick={() => {}}><Grid /></IconBtn>
    <IconBtn title="27px — control cluster" size={27} onClick={() => {}}><Grid /></IconBtn>
    <IconBtn title="20px — inline row control" size={20} onClick={() => {}}><Grid /></IconBtn>
  </div>
);

// `spin` rotates the child icon in place for an in-flight action — combine
// with `active` so a running control reads as lumen-tinted, not neutral.
export const Spinning = () => (
  <div style={stage}>
    <IconBtn title="Reprocessing…" active spin onClick={() => {}}><Refresh /></IconBtn>
  </div>
);

// Disabled — nothing to act on, or the action is already running.
export const Disabled = () => (
  <div style={stage}>
    <IconBtn title="Nothing to delete" tone="danger" disabled onClick={() => {}}><Trash /></IconBtn>
  </div>
);
