import React, { useState } from 'react';
import { OutputCard, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { width: 340, background: AP.base, padding: 16, display: 'flex', flexDirection: 'column', gap: 9 };

export const Caption = () => (
  <div style={stage}>
    <OutputCard
      o={{ output_type: 'caption', model_name: 'blip', model_version: 'image-captioning-base', payload: { text: 'A golden retriever sitting on a wooden dock at sunset.' } }}
    />
  </div>
);

// Detections are interactive: each row has a checkbox (hides its boxes on the
// bbox overlay elsewhere on the page) and a hover state — both driven here so
// they actually respond, exactly as they do wired into ImageDetails.
export const DetectionsInteractive = () => {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hovered, setHovered] = useState<string | null>(null);
  return (
    <div style={stage}>
      <OutputCard
        o={{
          output_type: 'detections',
          model_name: 'yolo',
          model_version: 'v8n',
          payload: {
            detections: [
              { label: 'car', confidence: 0.89 },
              { label: 'car', confidence: 0.74 },
              { label: 'person', confidence: 0.85 },
              { label: 'motorcycle', confidence: 0.47 },
            ],
          },
        }}
        detectionState={{
          hiddenLabels: hidden,
          hoveredLabel: hovered,
          toggleLabel: (name) =>
            setHidden((prev) => {
              const next = new Set(prev);
              next.has(name) ? next.delete(name) : next.add(name);
              return next;
            }),
          setHoveredLabel: setHovered,
        }}
      />
    </div>
  );
};

export const DetectionsEmpty = () => (
  <div style={stage}>
    <OutputCard o={{ output_type: 'detections', model_name: 'opencv_haar', model_version: 'frontalface_default', payload: { detections: [] } }} />
  </div>
);

export const Classification = () => (
  <div style={stage}>
    <OutputCard
      o={{
        output_type: 'labels',
        model_name: 'resnet',
        model_version: 'v1',
        payload: { labels: [{ label: 'outdoor', confidence: 0.94 }, { label: 'daytime', confidence: 0.81 }] },
      }}
    />
  </div>
);

export const OcrText = () => (
  <div style={stage}>
    <OutputCard
      o={{ output_type: 'ocr', model_name: 'tesseract', model_version: '5.3', payload: { text: 'OPEN\n9AM – 6PM\nMON – SAT' } }}
    />
  </div>
);

export const WrittenImage = () => (
  <div style={stage}>
    <OutputCard
      o={{
        output_type: 'written_image',
        model_name: 'image_write',
        model_version: 'v1',
        payload: { written_image: { path: '/photos/pixquery_output/ee283d8ab0dd31f6f18d33ffc4dfab99.jpg', width: 736, height: 1308, format: 'JPEG' } },
      }}
    />
  </div>
);
