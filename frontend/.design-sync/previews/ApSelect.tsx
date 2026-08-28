import React, { useState } from 'react';
import { ApSelect, AP } from 'pixquery-aperture';

const stage: React.CSSProperties = { padding: 16, background: AP.base, maxWidth: 320, display: 'flex', flexDirection: 'column', gap: 12 };

// Workspace picker — the common case, a short list of real names.
export const WorkspacePicker = () => {
  const [v, setV] = useState('living-room-photos');
  return (
    <div style={stage}>
      <ApSelect value={v} onChange={(e) => setV(e.target.value)}>
        <option value="living-room-photos">living-room-photos</option>
        <option value="trip-to-kyoto">trip-to-kyoto</option>
        <option value="pixquery-output">pixquery_output</option>
      </ApSelect>
    </div>
  );
};

// Role assignment — the other real use, a short enum of member roles.
export const RolePicker = () => (
  <div style={stage}>
    <ApSelect defaultValue="editor" onChange={() => {}}>
      <option value="viewer">Viewer</option>
      <option value="editor">Editor</option>
    </ApSelect>
  </div>
);
