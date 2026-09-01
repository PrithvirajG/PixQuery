import React, { useState } from 'react';
import { StageCard, OutputBody, outputIcon, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { width: 340, background: AP.base, padding: 16, display: 'flex', flexDirection: 'column', gap: 9 };

// Three stages of one pipeline run, numbered in order — the shape ImageDetails
// composes for a completed multi-node pipeline (object detection →
// classification → captioning). Each stage owns its own page-visibility eye
// and its type glyph (`outputIcon`), so stages read apart at a glance.
export const ThreeStages = () => {
  const [hidden, setHidden] = useState<Set<number>>(new Set([1]));
  const toggle = (i: number) =>
    setHidden((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  const detections = { output_type: 'detections', model_name: 'yolo', payload: { detections: [{ label: 'car', confidence: 0.89 }, { label: 'person', confidence: 0.85 }] } };
  const labels = { output_type: 'labels', model_name: 'resnet', payload: { labels: [{ label: 'outdoor', confidence: 0.94 }] } };
  const caption = { output_type: 'caption', model_name: 'blip', payload: { text: 'A busy street with cars and pedestrians.' } };
  return (
    <div style={stage}>
      <StageCard index={1} total={3} name="Detections" icon={outputIcon(detections)} trailing="yolo · v8n" hidden={hidden.has(0)} onToggleHidden={() => toggle(0)}>
        <OutputBody o={detections} />
      </StageCard>
      <StageCard index={2} total={3} name="Classification" icon={outputIcon(labels)} trailing="resnet · v1" hidden={hidden.has(1)} onToggleHidden={() => toggle(1)}>
        <OutputBody o={labels} />
      </StageCard>
      <StageCard index={3} total={3} name="Caption" icon={outputIcon(caption)} trailing="blip · base" hidden={hidden.has(2)} onToggleHidden={() => toggle(2)}>
        <OutputBody o={caption} />
      </StageCard>
    </div>
  );
};

// A single-stage pipeline omits the "i/total" badge entirely — it's only
// meaningful once there's more than one sibling to number against.
export const SingleStage = () => {
  const ocr = { output_type: 'ocr', model_name: 'tesseract', payload: { text: 'OPEN\n9AM – 6PM\nMON – SAT' } };
  return (
    <div style={stage}>
      <StageCard index={1} total={1} name="OCR text" icon={outputIcon(ocr)} trailing="tesseract · 5.3">
        <OutputBody o={ocr} />
      </StageCard>
    </div>
  );
};

// Hidden: the header stays (so you can still see the stage ran and re-show
// it), but its body — the record itself is untouched, only hidden — is gone.
export const HiddenStage = () => {
  const labels = { output_type: 'labels', model_name: 'resnet', payload: { labels: [{ label: 'outdoor', confidence: 0.94 }] } };
  return (
    <div style={stage}>
      <StageCard index={2} total={3} name="Classification" icon={outputIcon(labels)} trailing="resnet · v1" hidden onToggleHidden={() => {}}>
        <OutputBody o={labels} />
      </StageCard>
    </div>
  );
};

// The remaining two cases `outputIcon` handles: the "written image" glyph
// (the fifth recognized type — detections/labels/caption/ocr appear in the
// stories above), and the fallback for a type it doesn't recognize (a future
// output_type, or a legacy one) — no icon rather than a guess, since
// StageCard's `icon` prop is optional for exactly this reason.
export const WrittenImageAndUnknownType = () => {
  const written_image = { output_type: 'written_image', model_name: 'image_write', payload: {} };
  return (
    <div style={stage}>
      <StageCard index={1} total={1} name="Written image" icon={outputIcon(written_image)} trailing="image_write · v1">
        <div />
      </StageCard>
      <StageCard index={1} total={1} name="Unrecognized type" icon={outputIcon({ output_type: 'depth_map' })} trailing="future node">
        <div />
      </StageCard>
    </div>
  );
};
