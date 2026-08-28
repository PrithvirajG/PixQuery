import React, { useState } from 'react';
import { PipelineSection, OutputCard, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { width: 380, background: AP.base, padding: 16 };

// A completed run, expanded, showing its real outputs — a detections card and
// a caption card, exactly as ImageDetails.js composes them as `children`.
export const CompletedExpanded = () => {
  const [on, setOn] = useState(true);
  return (
    <div style={stage}>
      <PipelineSection
        section={{ name: 'Object Detection', id: '7db59ce5', state: 'completed', model: '2 outputs', hasOutputs: true }}
        on={on}
        toggle={() => setOn((v) => !v)}
        onProcess={() => {}}
        onDelete={() => {}}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <OutputCard
            o={{
              output_type: 'detections',
              model_name: 'yolo',
              model_version: 'v8n',
              payload: { detections: [{ label: 'car', confidence: 0.89 }, { label: 'person', confidence: 0.85 }] },
            }}
          />
          <OutputCard
            o={{ output_type: 'caption', model_name: 'blip', model_version: 'base', payload: { text: 'A busy street with cars and pedestrians.' } }}
          />
        </div>
      </PipelineSection>
    </div>
  );
};

// Never run: collapsed, no outputs yet, the Process button is the only action.
export const NotStartedCollapsed = () => {
  const [on, setOn] = useState(false);
  return (
    <div style={stage}>
      <PipelineSection
        section={{ name: 'Face Detection', state: 'not_started', model: '0 outputs', hasOutputs: false }}
        on={on}
        toggle={() => setOn((v) => !v)}
        onProcess={() => {}}
      >
        <div />
      </PipelineSection>
    </div>
  );
};

// A run in progress reports its stage — "stage 2/3 · captioning" — live progress
// inside a single dispatch, distinct from the outer Queued/Processing state.
export const ProcessingWithStage = () => (
  <div style={stage}>
    <PipelineSection
      section={{
        name: 'Full Analysis',
        state: 'processing',
        stage: { index: 2, total: 3, node_type: 'captioning' },
        model: 'working…',
        hasOutputs: true,
      }}
      on={false}
      toggle={() => {}}
      processing
      onDelete={() => {}}
      deleting={false}
    >
      <div />
    </PipelineSection>
  </div>
);

// A failed run surfaces its error inline, and can be retried in place.
export const Failed = () => (
  <div style={stage}>
    <PipelineSection
      section={{
        name: 'OCR',
        state: 'failed',
        lastError: 'Tesseract binary not found on PATH',
        model: '0 outputs',
        hasOutputs: false,
      }}
      on={false}
      toggle={() => {}}
      onProcess={() => {}}
    >
      <div />
    </PipelineSection>
  </div>
);

// A pipeline no longer attached to the workspace: read-only history, its
// outputs can still be viewed or cleared but not re-run.
export const Detached = () => (
  <div style={stage}>
    <PipelineSection
      section={{ name: 'Legacy Classifier', state: 'completed', detached: true, model: '1 output', hasOutputs: true }}
      on={true}
      toggle={() => {}}
      onDelete={() => {}}
    >
      <OutputCard
        o={{ output_type: 'labels', model_name: 'resnet', model_version: 'v1', payload: { labels: [{ label: 'outdoor', confidence: 0.91 }] } }}
      />
    </PipelineSection>
  </div>
);
