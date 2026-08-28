import React from 'react';
import { ActBtn, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, display: 'inline-flex', gap: 10 };

// The neutral row action — "Edit", "Statistics" on a workspace/pipeline card.
export const Default = () => (
  <div style={stage}>
    <ActBtn onClick={() => {}}>Statistics</ActBtn>
  </div>
);

// `accent` marks a row action as the Lumen-highlighted one among several —
// e.g. "Retry" standing out next to a plain "Edit".
export const AccentAndDefaultTogether = () => (
  <div style={stage}>
    <ActBtn accent onClick={() => {}}>↻ Retry</ActBtn>
    <ActBtn onClick={() => {}}>Edit</ActBtn>
  </div>
);

export const Disabled = () => (
  <div style={stage}>
    <ActBtn disabled title="Already running">↻ Retry</ActBtn>
  </div>
);

const spinnerIcon = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 12a8 8 0 1 1-2.34-5.66" />
    <path d="M20 4v4.5h-4.5" />
  </svg>
);

// `tone="danger"` — the STATUS.err treatment for a destructive row action
// (Delete a workspace/pipeline output), shown next to its neutral siblings so
// the contrast reads clearly.
export const DangerTone = () => (
  <div style={stage}>
    <ActBtn onClick={() => {}}>{spinnerIcon}Edit</ActBtn>
    <ActBtn tone="danger" onClick={() => {}}>{spinnerIcon}Delete</ActBtn>
  </div>
);

// `loading` swaps the whole button content for a spinning icon + a
// present-progressive `loadingLabel`, and forces the button disabled — one
// per tone, since each keeps its own dimmed palette while working.
export const Loading = () => (
  <div style={stage}>
    <ActBtn accent loading loadingLabel="Retrying…" onClick={() => {}}>{spinnerIcon}Retry</ActBtn>
    <ActBtn loading loadingLabel="Saving…" onClick={() => {}}>{spinnerIcon}Edit</ActBtn>
    <ActBtn tone="danger" loading loadingLabel="Deleting…" onClick={() => {}}>{spinnerIcon}Delete</ActBtn>
  </div>
);
