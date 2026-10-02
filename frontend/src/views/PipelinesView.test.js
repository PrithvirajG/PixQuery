import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import ModelManagementView from './PipelinesView';

jest.mock('axios');

// Node-library entries as GET /pipeline-nodes returns them: the stored node plus
// the executor's description (kind, executor, outputs_label, models).
const faceNode = {
  _id: 'lib-face',
  name: 'Face Detection',
  node_type: 'face_detection',
  context_inputs: ['image'],
  context_outputs: ['detections'],
  default_config: { confidence_threshold: 0.5 },
  kind: 'model',
  executor: 'FaceDetectionExecutor',
  outputs_label: 'bounding boxes',
  models: [
    { id: 'yunet', label: 'YuNet' },
    { id: 'scrfd', label: 'SCRFD' },
    { id: 'retinaface_r50', label: 'RetinaFace-R50' },
  ],
  default_model: 'retinaface_r50',
};

const vlmNode = {
  _id: 'lib-vlm',
  name: 'Vision Language Model',
  node_type: 'vision_language_model',
  context_inputs: ['image'],
  context_outputs: ['caption'],
  default_config: { prompt: 'Describe this image in one concise sentence.' },
  kind: 'model',
  executor: 'VisionLanguageModelExecutor',
  outputs_label: 'text caption',
  models: [
    { id: 'blip', label: 'BLIP', supports_prompt: false },
    { id: 'qwen2_vl_2b', label: 'Qwen2-VL-2B-Instruct', supports_prompt: true },
    { id: 'moondream2', label: 'Moondream2', supports_prompt: true },
  ],
  default_model: 'blip',
};

const resizeNode = {
  _id: 'lib-resize',
  name: 'Resize',
  node_type: 'resize',
  context_inputs: ['image'],
  context_outputs: ['image'],
  default_config: { width: 640, height: 640 },
  kind: 'transform',
  executor: 'ResizeExecutor',
  outputs_label: 'image',
  models: [],
  default_model: null,
};

function pipelineWith(node) {
  return {
    _id: 'pl-1',
    name: 'Faces',
    nodes: [{ node_id: 'n0', pipeline_node_id: node._id, config_overrides: {}, position: { x: 0, y: 0 } }],
    edges: [],
  };
}

function mockGets(pipeline) {
  axios.get.mockImplementation((url) => {
    if (url.endsWith('/pipelines')) return Promise.resolve({ data: [pipeline] });
    if (url.endsWith('/pipeline-nodes')) return Promise.resolve({ data: [faceNode, resizeNode, vlmNode] });
    if (url.endsWith('/workspaces')) return Promise.resolve({ data: [] });
    return Promise.reject(new Error('unexpected url ' + url));
  });
}

function renderView() {
  return render(
    <MemoryRouter>
      <ModelManagementView />
    </MemoryRouter>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe('PipelinesView node inspector', () => {
  test('model node shows a Model dropdown from the backend list, defaulted', async () => {
    mockGets(pipelineWith(faceNode));
    renderView();

    const select = await screen.findByRole('combobox', { name: 'Model' });
    const options = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(options).toEqual(['YuNet', 'SCRFD', 'RetinaFace-R50']);
    expect(select.value).toBe('retinaface_r50');
  });

  test('stage type, executor and outputs are shown read-only', async () => {
    mockGets(pipelineWith(faceNode));
    renderView();

    await screen.findByText('FaceDetectionExecutor');
    expect(screen.getByText('bounding boxes')).toBeInTheDocument();
    expect(screen.getAllByTitle('Read-only').length).toBe(4);
  });

  test('transform node has no Model dropdown', async () => {
    mockGets(pipelineWith(resizeNode));
    renderView();

    await screen.findByText('ResizeExecutor');
    expect(screen.queryByRole('combobox', { name: 'Model' })).not.toBeInTheDocument();
  });

  test('choosing a model is saved on the pipeline node', async () => {
    mockGets(pipelineWith(faceNode));
    axios.put.mockResolvedValue({ data: {} });
    renderView();

    const select = await screen.findByRole('combobox', { name: 'Model' });
    fireEvent.change(select, { target: { value: 'yunet' } });
    fireEvent.click(screen.getByText('✓ Save pipeline'));

    await waitFor(() => expect(axios.put).toHaveBeenCalled());
    const [url, body] = axios.put.mock.calls[0];
    expect(url).toMatch(/\/pipelines\/pl-1$/);
    expect(body.nodes[0].model).toBe('yunet');
  });

  test('a model saved on the node is preselected', async () => {
    const pipeline = pipelineWith(faceNode);
    pipeline.nodes[0].model = 'scrfd';
    mockGets(pipeline);
    renderView();

    const select = await screen.findByRole('combobox', { name: 'Model' });
    expect(select.value).toBe('scrfd');
  });

  test('adding a stage pins its default model', async () => {
    mockGets(pipelineWith(resizeNode));
    axios.put.mockResolvedValue({ data: {} });
    renderView();

    await screen.findByText('ResizeExecutor');
    fireEvent.click(screen.getByText('+ Add stage'));
    const paletteItem = screen
      .getAllByRole('button')
      .find((b) => b.textContent.includes('Face Detection'));
    fireEvent.click(paletteItem);

    // the new node is selected, showing its default model
    expect((await screen.findByRole('combobox', { name: 'Model' })).value).toBe('retinaface_r50');
    fireEvent.click(screen.getByText('✓ Save pipeline'));

    await waitFor(() => expect(axios.put).toHaveBeenCalled());
    const added = axios.put.mock.calls[0][1].nodes[1];
    expect(added.pipeline_node_id).toBe('lib-face');
    expect(added.model).toBe('retinaface_r50');
  });

  test('duplicating a pipeline keeps each node’s model', async () => {
    const pipeline = pipelineWith(faceNode);
    pipeline.nodes[0].model = 'yunet';
    mockGets(pipeline);
    axios.post.mockResolvedValue({ data: { _id: 'pl-2' } });
    renderView();

    await screen.findByRole('combobox', { name: 'Model' });
    fireEvent.click(screen.getByText('⧉ Duplicate'));

    await waitFor(() => expect(axios.post).toHaveBeenCalled());
    const [url, body] = axios.post.mock.calls[0];
    expect(url).toMatch(/\/pipelines$/);
    expect(body.nodes[0].model).toBe('yunet');
  });

  test('outputs fall back to the raw context keys without a label', async () => {
    const unlabelled = { ...faceNode, outputs_label: '' };
    axios.get.mockImplementation((url) => {
      if (url.endsWith('/pipelines')) return Promise.resolve({ data: [pipelineWith(unlabelled)] });
      if (url.endsWith('/pipeline-nodes')) return Promise.resolve({ data: [unlabelled] });
      if (url.endsWith('/workspaces')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });
    renderView();

    await screen.findByText('FaceDetectionExecutor');
    const outputs = screen.getAllByTitle('Read-only')[3];
    expect(outputs.textContent).toContain('detections');
  });
});

describe('PipelinesView Prompt field (Vision Language Model)', () => {
  test('no Prompt field for a model that does not support one (default: BLIP)', async () => {
    mockGets(pipelineWith(vlmNode));
    renderView();

    await screen.findByRole('combobox', { name: 'Model' });
    expect(screen.queryByRole('textbox', { name: 'Prompt' })).not.toBeInTheDocument();
  });

  test('Prompt field appears for a prompt-capable model, defaulted from default_config', async () => {
    mockGets(pipelineWith(vlmNode));
    renderView();

    const select = await screen.findByRole('combobox', { name: 'Model' });
    fireEvent.change(select, { target: { value: 'qwen2_vl_2b' } });

    const prompt = await screen.findByRole('textbox', { name: 'Prompt' });
    expect(prompt.value).toBe('Describe this image in one concise sentence.');
  });

  test('switching back to BLIP hides the Prompt field again', async () => {
    mockGets(pipelineWith(vlmNode));
    renderView();

    const select = await screen.findByRole('combobox', { name: 'Model' });
    fireEvent.change(select, { target: { value: 'qwen2_vl_2b' } });
    await screen.findByRole('textbox', { name: 'Prompt' });

    fireEvent.change(select, { target: { value: 'blip' } });
    expect(screen.queryByRole('textbox', { name: 'Prompt' })).not.toBeInTheDocument();
  });

  test('editing the prompt and saving sends it in config_overrides', async () => {
    const pipeline = pipelineWith(vlmNode);
    pipeline.nodes[0].model = 'qwen2_vl_2b';
    mockGets(pipeline);
    axios.put.mockResolvedValue({ data: {} });
    renderView();

    const prompt = await screen.findByRole('textbox', { name: 'Prompt' });
    fireEvent.change(prompt, { target: { value: 'What brand or text is visible?' } });
    fireEvent.click(screen.getByText('✓ Save pipeline'));

    await waitFor(() => expect(axios.put).toHaveBeenCalled());
    const saved = axios.put.mock.calls[0][1].nodes[0];
    expect(saved.model).toBe('qwen2_vl_2b');
    expect(saved.config_overrides.prompt).toBe('What brand or text is visible?');
  });

  test('a saved prompt override is shown instead of the default', async () => {
    const pipeline = pipelineWith(vlmNode);
    pipeline.nodes[0].model = 'moondream2';
    pipeline.nodes[0].config_overrides = { prompt: 'Is there a person in this image?' };
    mockGets(pipeline);
    renderView();

    const prompt = await screen.findByRole('textbox', { name: 'Prompt' });
    expect(prompt.value).toBe('Is there a person in this image?');
  });
});
