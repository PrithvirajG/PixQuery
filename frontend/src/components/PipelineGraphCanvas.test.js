import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PipelineGraphCanvas from './PipelineGraphCanvas';

const library = [
  { _id: 'lib-face', name: 'Face Detection', node_type: 'face_detection' },
  { _id: 'lib-resize', name: 'Resize', node_type: 'resize' },
];
const baseNodes = [
  { node_id: 'n1', pipeline_node_id: 'lib-face', position: { x: 60, y: 40 } },
  { node_id: 'n2', pipeline_node_id: 'lib-resize', position: { x: 400, y: 40 } },
];
const edge = { edge_id: 'e1', from_node_id: 'n1', to_node_id: 'n2' };

function renderCanvas(props = {}) {
  const handlers = {
    onSelectNode: jest.fn(), onMoveNode: jest.fn(), onAddEdge: jest.fn(),
    onRemoveEdge: jest.fn(), onRemoveNode: jest.fn(),
  };
  const utils = render(
    <PipelineGraphCanvas nodes={baseNodes} edges={[edge]} nodeLibrary={library} selectedNodeId={null} {...handlers} {...props} />
  );
  // jsdom's getBoundingClientRect is all zeros, so clientX/Y == canvas coords.
  const canvas = utils.container.firstChild;
  const card = (name) => screen.getByText(name).parentElement.parentElement;
  return { ...utils, ...handlers, canvas, card };
}

describe('PipelineGraphCanvas', () => {
  test('renders node names/types and falls back for an unknown library entry', () => {
    renderCanvas({ nodes: [...baseNodes, { node_id: 'n3', pipeline_node_id: 'lib-gone', position: { x: 0, y: 200 } }] });
    expect(screen.getByText('Face Detection')).toBeInTheDocument();
    expect(screen.getByText('face_detection')).toBeInTheDocument();
    expect(screen.getByText('unknown node')).toBeInTheDocument();
    expect(screen.getByText('lib-gone')).toBeInTheDocument();
  });

  test('uses styleForType for the node icon', () => {
    renderCanvas({ styleForType: (t) => ({ c: '#fff', line: '#000', icon: t === 'face_detection' ? '✦' : '◧' }) });
    expect(screen.getByText('✦')).toBeInTheDocument();
    expect(screen.getByText('◧')).toBeInTheDocument();
  });

  test('clicking a node selects it; clicking empty canvas clears selection', () => {
    const { onSelectNode, canvas, card } = renderCanvas();
    fireEvent.click(card('Resize'));
    expect(onSelectNode).toHaveBeenLastCalledWith('n2');
    fireEvent.click(canvas);
    expect(onSelectNode).toHaveBeenLastCalledWith(null);
  });

  test('remove buttons call their handlers without selecting', () => {
    const { onRemoveNode, onRemoveEdge, onSelectNode } = renderCanvas();
    fireEvent.click(screen.getAllByTitle('Remove node')[0]);
    expect(onRemoveNode).toHaveBeenCalledWith('n1');
    fireEvent.click(screen.getByTitle('Remove connection'));
    expect(onRemoveEdge).toHaveBeenCalledWith(edge);
    expect(onSelectNode).not.toHaveBeenCalled();
  });

  test('edges pointing at a missing node are not drawn', () => {
    renderCanvas({ edges: [{ edge_id: 'e9', from_node_id: 'n1', to_node_id: 'ghost' }] });
    expect(screen.queryByTitle('Remove connection')).not.toBeInTheDocument();
  });

  test('dragging a node commits its new position on mouse-up', () => {
    const { onMoveNode, onSelectNode, canvas, card } = renderCanvas();
    fireEvent.mouseDown(card('Face Detection'), { button: 0, clientX: 100, clientY: 50 }); // grab offset (40, 10)
    expect(onSelectNode).toHaveBeenCalledWith('n1');
    fireEvent.mouseMove(canvas, { clientX: 200, clientY: 150 });
    fireEvent.mouseUp(canvas);
    expect(onMoveNode).toHaveBeenCalledWith('n1', { x: 160, y: 140 });
  });

  test('drag is clamped at the canvas origin', () => {
    const { onMoveNode, canvas, card } = renderCanvas();
    fireEvent.mouseDown(card('Face Detection'), { button: 0, clientX: 100, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 5, clientY: 2 });
    fireEvent.mouseUp(canvas);
    expect(onMoveNode).toHaveBeenCalledWith('n1', { x: 0, y: 0 });
  });

  test('right-button and leaving the canvas do not move nodes', () => {
    const { onMoveNode, canvas, card } = renderCanvas();
    fireEvent.mouseDown(card('Face Detection'), { button: 2, clientX: 100, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 300, clientY: 300 });
    fireEvent.mouseUp(canvas);
    fireEvent.mouseDown(card('Face Detection'), { button: 0, clientX: 100, clientY: 50 });
    fireEvent.mouseLeave(canvas);
    fireEvent.mouseUp(canvas);
    expect(onMoveNode).not.toHaveBeenCalled();
  });

  test('dragging from an output port onto another input adds an edge', () => {
    const { onAddEdge } = renderCanvas({ edges: [] });
    fireEvent.mouseDown(screen.getAllByTitle('Drag to connect')[0], { clientX: 248, clientY: 69 });
    fireEvent.mouseUp(screen.getAllByTitle('Drop to connect')[1]);
    expect(onAddEdge).toHaveBeenCalledWith({ from_node_id: 'n1', to_node_id: 'n2' });
  });

  test('dropping on its own input, or releasing on empty canvas, adds nothing', () => {
    const { onAddEdge, canvas } = renderCanvas({ edges: [] });
    fireEvent.mouseDown(screen.getAllByTitle('Drag to connect')[0]);
    fireEvent.mouseUp(screen.getAllByTitle('Drop to connect')[0]);
    fireEvent.mouseDown(screen.getAllByTitle('Drag to connect')[0]);
    fireEvent.mouseUp(canvas);
    fireEvent.mouseUp(screen.getAllByTitle('Drop to connect')[1]); // pending already cancelled
    expect(onAddEdge).not.toHaveBeenCalled();
  });
});
