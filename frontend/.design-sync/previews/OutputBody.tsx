import React from 'react';
import { OutputBody, AP } from 'pixquery-aperture';

// OutputBody has no card chrome of its own (OutputCard supplies the header) —
// wrap plainly, the way OutputCard uses it internally.
const stage: React.CSSProperties = { width: 300, padding: 16, background: AP.card, borderRadius: 9 };

export const Caption = () => (
  <div style={stage}>
    <OutputBody o={{ output_type: 'caption', payload: { text: 'A golden retriever sitting on a wooden dock at sunset.' } }} />
  </div>
);

// Detections aggregate repeats (2 cars → "car ×2") and sort by confidence.
export const Detections = () => (
  <div style={stage}>
    <OutputBody
      o={{ output_type: 'detections', payload: { detections: [
        { label: 'car', confidence: 0.89 },
        { label: 'car', confidence: 0.74 },
        { label: 'person', confidence: 0.85 },
      ] } }}
    />
  </div>
);

export const DetectionsEmpty = () => (
  <div style={stage}>
    <OutputBody o={{ output_type: 'detections', payload: { detections: [] } }} />
  </div>
);

export const Labels = () => (
  <div style={stage}>
    <OutputBody o={{ output_type: 'labels', payload: { labels: [{ label: 'outdoor', confidence: 0.94 }, { label: 'daytime', confidence: 0.81 }] } }} />
  </div>
);

// Any output_type OutputBody doesn't recognize falls back to its `summary` line.
export const UnknownTypeFallback = () => (
  <div style={stage}>
    <OutputBody o={{ output_type: 'embedding', summary: 'Output recorded.' }} />
  </div>
);
