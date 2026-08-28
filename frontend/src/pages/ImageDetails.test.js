import React from 'react';
import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import ImageDetails from './ImageDetails';
import { subscribeToEvents } from '../lib/eventSocket';

jest.mock('axios');

// The socket itself is covered in lib/eventSocket.test.js. Here we only need a
// handle on the subscriber so a test can push events as if the backend sent them.
jest.mock('../lib/eventSocket', () => ({
  subscribeToEvents: jest.fn(() => () => {}),
}));

/** Deliver an event to the page's subscriber, wrapped so React batches the update. */
async function emit(event) {
  const handler = subscribeToEvents.mock.calls.at(-1)[0];
  await waitFor(() => expect(handler).toBeDefined());
  await act(async () => {
    handler(event);
  });
}

const API = 'http://localhost:8000';

// Two detections of different labels so per-label toggling is observable.
const detections = [
  { label: 'person', confidence: 0.9, bbox: [100, 100, 50, 80] },
  { label: 'handbag', confidence: 0.37, bbox: [200, 150, 30, 30] },
];

function detail(overrides = {}) {
  return {
    _id: 'asset-1',
    current_path: '/photos/cat.jpg',
    size_bytes: 189_440,
    mime_type: 'image/jpeg',
    first_seen_at: '2026-01-02T03:04:05Z',
    metadata: { width: 736, height: 1308 },
    description: '',
    detections,
    provenance: { pipelines: [] },
    ...overrides,
  };
}

function pipeline(overrides = {}) {
  return {
    pipeline_id: 'pl-1',
    name: 'Test Pipeline',
    attached: true,
    state: 'completed',
    status: 'completed',
    last_error: null,
    outputs: [
      {
        output_type: 'detections',
        model_name: 'yolo',
        model_version: 'v8n',
        order: 0,
        payload: { detections },
      },
    ],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/image/asset-1']}>
      <Routes>
        <Route path="/image/:id" element={<ImageDetails />} />
      </Routes>
    </MemoryRouter>
  );
}

function mockDetail(data) {
  axios.get.mockImplementation((url) =>
    url.includes('/detail')
      ? Promise.resolve({ data })
      : Promise.reject(new Error('unexpected url ' + url))
  );
}

// The overlay only renders once the <img> reports its natural size. jsdom makes
// naturalWidth/Height read-only getters, so define them before firing load.
function loadImage(container, width = 736, height = 1308) {
  const img = container.querySelector('img');
  Object.defineProperty(img, 'naturalWidth', { value: width, configurable: true });
  Object.defineProperty(img, 'naturalHeight', { value: height, configurable: true });
  fireEvent.load(img);
  return img;
}

beforeEach(() => {
  jest.clearAllMocks();
  // The rail width persists deliberately, so clear it between tests to keep each
  // one starting from the default rather than inheriting the previous one's drag.
  localStorage.clear();
});

describe('ImageDetails — file info', () => {
  test('always shows core file rows', async () => {
    mockDetail(detail());
    renderPage();

    await waitFor(() => expect(screen.getByText('path')).toBeInTheDocument());
    // Dimensions render twice: the photo's caption chip and the File Info row.
    expect(screen.getAllByText('736 × 1308').length).toBeGreaterThan(0);
    expect(screen.getByText('185.0 KB · JPEG')).toBeInTheDocument();
  });

  test('renders EXIF rows that are present on the image', async () => {
    mockDetail(
      detail({
        metadata: {
          width: 736,
          height: 1308,
          camera_make: 'OPPO',
          camera_model: 'Find X8',
          gps_latitude: 12.34567,
          gps_longitude: 76.54321,
          focal_length: 5.6,
          f_number: 1.8,
          exposure_time: 0.008,
          iso: 400,
          lens_model: 'Wide',
        },
      })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('camera')).toBeInTheDocument());
    expect(screen.getByText('OPPO Find X8')).toBeInTheDocument();
    expect(screen.getByText('geo-location')).toBeInTheDocument();
    expect(screen.getByText('12.34567, 76.54321')).toBeInTheDocument();
    expect(screen.getByText('5.6mm')).toBeInTheDocument();
    expect(screen.getByText('f/1.8')).toBeInTheDocument();
    expect(screen.getByText('1/125s')).toBeInTheDocument();
    expect(screen.getByText('400')).toBeInTheDocument();
  });

  test('omits EXIF rows the image does not have', async () => {
    mockDetail(detail({ metadata: { width: 10, height: 10 } }));
    renderPage();

    await waitFor(() => expect(screen.getByText('path')).toBeInTheDocument());
    expect(screen.queryByText('camera')).not.toBeInTheDocument();
    expect(screen.queryByText('geo-location')).not.toBeInTheDocument();
    expect(screen.queryByText('iso')).not.toBeInTheDocument();
  });
});

describe('ImageDetails — detection overlay', () => {
  const withDetections = () =>
    detail({ provenance: { pipelines: [pipeline()] } });

  test('draws a box per detection', async () => {
    mockDetail(withDetections());
    const { container } = renderPage();

    await waitFor(() => expect(screen.getByText('person')).toBeInTheDocument());
    // Image must report natural dimensions before the SVG overlay renders.
    loadImage(container);

    await waitFor(() => expect(container.querySelectorAll('svg rect')).toHaveLength(2));
  });

  test('unchecking a label removes only that label’s box', async () => {
    mockDetail(withDetections());
    const { container } = renderPage();

    await waitFor(() => expect(screen.getByText('person')).toBeInTheDocument());
    loadImage(container);
    await waitFor(() => expect(container.querySelectorAll('svg rect')).toHaveLength(2));

    // Rows are sorted by confidence: person (0.90) first, handbag (0.37) second.
    const boxes = screen.getAllByRole('checkbox');
    expect(boxes).toHaveLength(2);
    fireEvent.click(boxes[0]);

    await waitFor(() => expect(container.querySelectorAll('svg rect')).toHaveLength(1));
    expect(boxes[0]).not.toBeChecked();
    expect(boxes[1]).toBeChecked();
  });

  test('unchecking every label hides the overlay entirely', async () => {
    mockDetail(withDetections());
    const { container } = renderPage();

    await waitFor(() => expect(screen.getByText('person')).toBeInTheDocument());
    loadImage(container);
    await waitFor(() => expect(container.querySelectorAll('svg rect')).toHaveLength(2));

    screen.getAllByRole('checkbox').forEach((box) => fireEvent.click(box));
    await waitFor(() => expect(container.querySelectorAll('svg rect')).toHaveLength(0));
  });
});

describe('ImageDetails — pipeline state', () => {
  test('a never-run attached pipeline still gets a section and a Process button', async () => {
    // The regression that started all this: no outputs used to mean no section,
    // so there was no way to trigger the pipeline at all.
    mockDetail(
      detail({
        detections: [],
        provenance: {
          pipelines: [pipeline({ state: 'not_started', status: null, outputs: [] })],
        },
      })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());
    expect(screen.getByText('Not started')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Process/ })).toBeEnabled();
  });

  test('a completed pipeline offers Reprocess', async () => {
    mockDetail(detail({ provenance: { pipelines: [pipeline()] } }));
    renderPage();

    await waitFor(() => expect(screen.getByText('Completed')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Reprocess/ })).toBeEnabled();
  });

  test.each(['queued', 'processing'])('the button is disabled while %s', async (state) => {
    mockDetail(
      detail({
        detections: [],
        provenance: { pipelines: [pipeline({ state, outputs: [] })] },
      })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Process/ })).toBeDisabled();
  });

  test('a failed pipeline shows its error message', async () => {
    mockDetail(
      detail({
        detections: [],
        provenance: {
          pipelines: [
            pipeline({
              state: 'failed',
              outputs: [],
              last_error: { message: 'model weights missing' },
            }),
          ],
        },
      })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('Failed')).toBeInTheDocument());
    expect(screen.getByText('model weights missing')).toBeInTheDocument();
  });

  test('a detached pipeline is badged and offers no Process button', async () => {
    mockDetail(
      detail({ provenance: { pipelines: [pipeline({ attached: false })] } })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('Detached')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /Process/ })).not.toBeInTheDocument();
  });

  test('explains when no pipelines are attached to the workspace', async () => {
    mockDetail(detail({ detections: [] }));
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/No pipelines are attached/)).toBeInTheDocument()
    );
  });
});

describe('ImageDetails — triggering a run', () => {
  test('Process posts to the reprocess endpoint with the pipeline id', async () => {
    mockDetail(
      detail({
        detections: [],
        provenance: {
          pipelines: [pipeline({ state: 'not_started', outputs: [] })],
        },
      })
    );
    axios.post.mockResolvedValue({ data: {} });

    renderPage();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Process/ }));

    await waitFor(() =>
      expect(axios.post).toHaveBeenCalledWith(`${API}/images/asset-1/reprocess`, {
        pipeline_id: 'pl-1',
      })
    );
  });

  test('surfaces a conflict without blanking the page', async () => {
    mockDetail(
      detail({
        detections: [],
        provenance: {
          pipelines: [pipeline({ state: 'not_started', outputs: [] })],
        },
      })
    );
    axios.post.mockRejectedValue({
      response: { data: { message: 'This pipeline is already queued for this image' } },
    });

    renderPage();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Process/ }));

    await waitFor(() =>
      expect(
        screen.getByText('This pipeline is already queued for this image')
      ).toBeInTheDocument()
    );
    // The page itself must survive — the notice is non-fatal.
    expect(screen.getByText('Test Pipeline')).toBeInTheDocument();
  });
});

describe('ImageDetails — deleting a pipeline’s outputs', () => {
  const withOutputs = () =>
    detail({ workspace_id: 'ws-1', provenance: { pipelines: [pipeline()] } });

  test('asks before deleting, and does nothing if declined', async () => {
    mockDetail(withOutputs());
    window.confirm = jest.fn(() => false);

    renderPage();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Delete outputs' }));

    expect(window.confirm).toHaveBeenCalled();
    expect(axios.delete).not.toHaveBeenCalled();
  });

  test('deletes this pipeline’s outputs for this image only', async () => {
    mockDetail(withOutputs());
    window.confirm = jest.fn(() => true);
    axios.delete.mockResolvedValue({ data: { outputs_deleted: 1 } });

    renderPage();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Delete outputs' }));

    await waitFor(() =>
      // Scoped to the image — not the workspace-wide clear on the workspaces route.
      expect(axios.delete).toHaveBeenCalledWith(`${API}/images/asset-1/outputs/pl-1`)
    );
  });

  test('is disabled when the pipeline has nothing stored to delete', async () => {
    mockDetail(
      detail({
        detections: [],
        provenance: { pipelines: [pipeline({ state: 'not_started', outputs: [] })] },
      })
    );
    renderPage();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    expect(screen.getByRole('button', { name: 'Delete outputs' })).toBeDisabled();
  });

  test('surfaces a failure without blanking the page', async () => {
    mockDetail(withOutputs());
    window.confirm = jest.fn(() => true);
    axios.delete.mockRejectedValue({
      response: { data: { message: 'Clearing pipeline outputs requires the editor role' } },
    });

    renderPage();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Delete outputs' }));

    await waitFor(() =>
      expect(
        screen.getByText('Clearing pipeline outputs requires the editor role')
      ).toBeInTheDocument()
    );
    expect(screen.getByText('Test Pipeline')).toBeInTheDocument();
  });
});

describe('ImageDetails — live updates', () => {
  const completed = () =>
    detail({ workspace_id: 'ws-1', provenance: { pipelines: [pipeline()] } });

  test('a queued event replaces the outputs with a loading placeholder', async () => {
    mockDetail(completed());
    const { container } = renderPage();
    // Wait for the outputs themselves: the section's pill renders one tick before
    // its body, which only appears once the per-pipeline toggle defaults to on.
    await waitFor(() => expect(screen.getByText('person')).toBeInTheDocument());
    expect(screen.getByText('Completed')).toBeInTheDocument();

    await emit({
      type: 'pipeline_state',
      asset_id: 'asset-1',
      workspace_id: 'ws-1',
      pipeline_id: 'pl-1',
      data: { state: 'queued' },
    });

    expect(screen.getByText('Queued')).toBeInTheDocument();
    // Stale results give way to shimmer rather than lingering as if current.
    expect(screen.queryByText('person')).not.toBeInTheDocument();
    expect(container.querySelectorAll('.ap-shimmer').length).toBeGreaterThan(0);
  });

  test('boxes for an in-flight pipeline are removed from the overlay', async () => {
    mockDetail(completed());
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByText('person')).toBeInTheDocument());
    loadImage(container);
    await waitFor(() => expect(container.querySelectorAll('svg rect')).toHaveLength(2));

    await emit({
      type: 'pipeline_state',
      asset_id: 'asset-1',
      workspace_id: 'ws-1',
      pipeline_id: 'pl-1',
      data: { state: 'processing' },
    });

    expect(container.querySelectorAll('svg rect')).toHaveLength(0);
  });

  test('stage events show progress within the run', async () => {
    mockDetail(completed());
    renderPage();
    await waitFor(() => expect(screen.getByText('Completed')).toBeInTheDocument());

    await emit({
      type: 'pipeline_stage',
      asset_id: 'asset-1',
      workspace_id: 'ws-1',
      pipeline_id: 'pl-1',
      data: { index: 2, total: 3, node_type: 'captioning' },
    });

    expect(screen.getByText(/stage 2\/3 · captioning/)).toBeInTheDocument();
  });

  test('a completed event refetches so real outputs replace the placeholder', async () => {
    mockDetail(completed());
    renderPage();
    await waitFor(() => expect(screen.getByText('Completed')).toBeInTheDocument());
    const before = axios.get.mock.calls.length;

    await emit({
      type: 'pipeline_state',
      asset_id: 'asset-1',
      workspace_id: 'ws-1',
      pipeline_id: 'pl-1',
      data: { state: 'completed' },
    });

    await waitFor(() => expect(axios.get.mock.calls.length).toBeGreaterThan(before));
  });

  test('events about a different image are ignored', async () => {
    mockDetail(completed());
    renderPage();
    await waitFor(() => expect(screen.getByText('Completed')).toBeInTheDocument());

    await emit({
      type: 'pipeline_state',
      asset_id: 'some-other-asset',
      workspace_id: 'ws-1',
      pipeline_id: 'pl-1',
      data: { state: 'queued' },
    });

    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.queryByText('Queued')).not.toBeInTheDocument();
  });

  test('a workspace-wide clear for another workspace is ignored', async () => {
    mockDetail(completed());
    renderPage();
    await waitFor(() => expect(screen.getByText('Completed')).toBeInTheDocument());
    const before = axios.get.mock.calls.length;

    await emit({
      type: 'outputs_cleared',
      asset_id: null,
      workspace_id: 'some-other-workspace',
      pipeline_id: 'pl-1',
      data: { scope: 'workspace' },
    });

    expect(axios.get.mock.calls.length).toBe(before);
  });

  test('a workspace-wide clear for this workspace refetches', async () => {
    mockDetail(completed());
    renderPage();
    await waitFor(() => expect(screen.getByText('Completed')).toBeInTheDocument());
    const before = axios.get.mock.calls.length;

    await emit({
      type: 'outputs_cleared',
      asset_id: null,
      workspace_id: 'ws-1',
      pipeline_id: 'pl-1',
      data: { scope: 'workspace' },
    });

    await waitFor(() => expect(axios.get.mock.calls.length).toBeGreaterThan(before));
  });

  test('unsubscribes on unmount so a closed page stops receiving events', async () => {
    const unsubscribe = jest.fn();
    subscribeToEvents.mockReturnValueOnce(unsubscribe);
    mockDetail(completed());

    const { unmount } = renderPage();
    await waitFor(() => expect(screen.getByText('Completed')).toBeInTheDocument());
    unmount();

    expect(unsubscribe).toHaveBeenCalled();
  });
});

describe('ImageDetails — resizable info rail', () => {
  const railOf = (container) =>
    container.querySelector('.ap-scroll');

  test('drag widens the rail', async () => {
    mockDetail(detail());
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByText('path')).toBeInTheDocument());

    const rail = railOf(container);
    const startWidth = parseInt(rail.style.width, 10);

    const handle = screen.getByRole('separator', { name: 'Resize info panel' });
    fireEvent.mouseDown(handle, { clientX: 800 });
    // Dragging left widens the rail, since it's anchored to the right edge.
    fireEvent.mouseMove(document, { clientX: 700 });
    fireEvent.mouseUp(document);

    expect(parseInt(railOf(container).style.width, 10)).toBe(startWidth + 100);
  });

  test('cannot be dragged narrower than its minimum', async () => {
    mockDetail(detail());
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByText('path')).toBeInTheDocument());

    const handle = screen.getByRole('separator', { name: 'Resize info panel' });
    fireEvent.mouseDown(handle, { clientX: 800 });
    fireEvent.mouseMove(document, { clientX: 5000 });
    fireEvent.mouseUp(document);

    expect(parseInt(railOf(container).style.width, 10)).toBe(280);
  });

  test('arrow keys resize it without a mouse', async () => {
    mockDetail(detail());
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByText('path')).toBeInTheDocument());

    const startWidth = parseInt(railOf(container).style.width, 10);
    const handle = screen.getByRole('separator', { name: 'Resize info panel' });
    fireEvent.keyDown(handle, { key: 'ArrowLeft' });

    expect(parseInt(railOf(container).style.width, 10)).toBe(startWidth + 16);
  });

  test('the chosen width is remembered', async () => {
    mockDetail(detail());
    const { container, unmount } = renderPage();
    await waitFor(() => expect(screen.getByText('path')).toBeInTheDocument());

    const handle = screen.getByRole('separator', { name: 'Resize info panel' });
    fireEvent.mouseDown(handle, { clientX: 800 });
    fireEvent.mouseMove(document, { clientX: 760 });
    fireEvent.mouseUp(document);
    const chosen = parseInt(railOf(container).style.width, 10);
    unmount();

    const second = renderPage();
    await waitFor(() => expect(screen.getByText('path')).toBeInTheDocument());
    expect(parseInt(railOf(second.container).style.width, 10)).toBe(chosen);
  });
});

describe('ImageDetails — load failure', () => {
  test('shows an error when the detail request fails', async () => {
    axios.get.mockRejectedValue(new Error('network down'));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Could not load image details/)).toBeInTheDocument()
    );
  });
});
