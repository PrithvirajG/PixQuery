import React from 'react';
import { ProcessButton, AP } from 'pixquery-aperture';

const row: React.CSSProperties = { padding: 16, background: AP.base, display: 'flex', alignItems: 'center', gap: 12 };
const label: React.CSSProperties = { fontFamily: AP.mono, fontSize: 11, color: AP.ink3 };

// Never run: enabled, offers to start it.
export const NotStarted = () => (
  <div style={row}>
    <ProcessButton state="not_started" onClick={() => {}} />
    <span style={label}>not_started</span>
  </div>
);

// Already has output: enabled, label flips to Reprocess (replaces old output).
export const Completed = () => (
  <div style={row}>
    <ProcessButton state="completed" onClick={() => {}} />
    <span style={label}>completed</span>
  </div>
);

// In flight — disabled, can't be dispatched twice.
export const Queued = () => (
  <div style={row}>
    <ProcessButton state="queued" onClick={() => {}} />
    <span style={label}>queued (disabled)</span>
  </div>
);

// A prior run failed — offers to try again.
export const Failed = () => (
  <div style={row}>
    <ProcessButton state="failed" onClick={() => {}} />
    <span style={label}>failed</span>
  </div>
);

// This client's own request is in flight (distinct from `state` being queued).
export const Busy = () => (
  <div style={row}>
    <ProcessButton state="not_started" onClick={() => {}} busy />
    <span style={label}>busy</span>
  </div>
);
