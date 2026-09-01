import React, { useState } from 'react';
import { PipelineSection, StageCard, OutputBody, outputIcon, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { width: 380, background: AP.base, padding: 16 };

// A completed run, expanded, showing its real outputs as numbered stages —
// exactly as ImageDetails.js composes them as `children`. The eye/reprocess/
// delete cluster replaces the old switch + text button + emoji trash: one
// shape, three jobs, colour is the only thing that separates them.
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
          {(() => {
            const detections = { output_type: 'detections', model_name: 'yolo', payload: { detections: [{ label: 'car', confidence: 0.89 }, { label: 'person', confidence: 0.85 }] } };
            const caption = { output_type: 'caption', model_name: 'blip', payload: { text: 'A busy street with cars and pedestrians.' } };
            return (
              <>
                <StageCard index={1} total={2} name="Detections" icon={outputIcon(detections)} trailing="yolo · v8n">
                  <OutputBody o={detections} />
                </StageCard>
                <StageCard index={2} total={2} name="Caption" icon={outputIcon(caption)} trailing="blip · base">
                  <OutputBody o={caption} />
                </StageCard>
              </>
            );
          })()}
        </div>
      </PipelineSection>
    </div>
  );
};

// Never run: the eye/reprocess cluster is the only way to trigger the
// pipeline at all — no separate Process button.
export const NotStarted = () => {
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

// A run in progress reports its stage — "stage 2/3 · captioning" — live
// progress inside a single dispatch. The reprocess control spins and locks
// while running, replacing the old disabled "⋯ Working" text button.
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
      onProcess={() => {}}
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

// A pipeline no longer attached to the workspace: reprocess disappears
// entirely (a two-control cluster) — the eye stays, so history is still
// readable, and delete stays enabled while outputs exist.
export const Detached = () => (
  <div style={stage}>
    <PipelineSection
      section={{ name: 'Legacy Classifier', state: 'completed', detached: true, model: '1 output', hasOutputs: true }}
      on={true}
      toggle={() => {}}
      onDelete={() => {}}
    >
      <StageCard
        index={1}
        total={1}
        name="Classification"
        icon={outputIcon({ output_type: 'labels' })}
        trailing="resnet · v1"
      >
        <OutputBody o={{ output_type: 'labels', model_name: 'resnet', payload: { labels: [{ label: 'outdoor', confidence: 0.91 }] } }} />
      </StageCard>
    </PipelineSection>
  </div>
);
