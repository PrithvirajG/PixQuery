import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import WorkspaceDetailView from './WorkspaceDetailView';

jest.mock('axios');

const ws = { _id: 'w1', name: 'Family', active: true, pipeline_ids: ['p1'] };
const pipelines = [
  { _id: 'p1', name: 'Faces', nodes: [{}, {}] },
  { _id: 'p2', name: 'OCR', nodes: [{}] },
];
const job = (pipeline_id, status, workspace_id = 'w1') => ({ _id: `${pipeline_id}-${status}-${Math.random()}`, pipeline_id, status, workspace_id, updated_at: '2026-09-01T00:00:00Z' });

function mockGets({ workspace = ws, jobs = [], fail = false } = {}) {
  axios.get.mockImplementation((url) => {
    if (fail) return Promise.reject(new Error('down'));
    if (url.endsWith('/workspaces/w1')) return Promise.resolve({ data: workspace });
    if (url.endsWith('/pipelines')) return Promise.resolve({ data: pipelines });
    if (url.includes('/stats/jobs/recent')) return Promise.resolve({ data: jobs });
    return Promise.reject(new Error('unexpected url ' + url));
  });
}

function renderView() {
  return render(
    <MemoryRouter initialEntries={['/workspaces/w1']}>
      <Routes>
        <Route path="/workspaces/:id" element={<WorkspaceDetailView />} />
        <Route path="/workspaces" element={<div>workspace list page</div>} />
        <Route path="/workspaces/:id/pipelines/:pipelineId/stats" element={<div>stats page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => jest.clearAllMocks());

describe('WorkspaceDetailView', () => {
  test('shows loading, then attached and available pipelines', async () => {
    mockGets();
    renderView();
    expect(screen.getByText('loading…')).toBeInTheDocument();
    expect(await screen.findByText('Faces')).toBeInTheDocument();
    expect(screen.getByText('OCR')).toBeInTheDocument();
    expect(screen.getByText('Attached pipelines')).toBeInTheDocument();
    expect(screen.getByText('Available')).toBeInTheDocument();
    expect(screen.getByText('2 nodes')).toBeInTheDocument();
    expect(screen.getByText('1 node')).toBeInTheDocument();
  });

  test('load failure offers a way back', async () => {
    mockGets({ fail: true });
    renderView();
    expect(await screen.findByText(/Failed to load workspace/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('‹ Workspaces'));
    expect(await screen.findByText('workspace list page')).toBeInTheDocument();
  });

  test('aggregates this workspace’s jobs per pipeline and ignores other workspaces', async () => {
    mockGets({
      jobs: [job('p1', 'completed'), job('p1', 'completed'), job('p1', 'failed'), job('p1', 'completed', 'other-ws')],
    });
    renderView();
    expect(await screen.findByText('1 failed · 2/3 completed')).toBeInTheDocument();
  });

  test('a processing job shows the in-flight bar', async () => {
    mockGets({ jobs: [job('p1', 'processing'), job('p1', 'completed')] });
    renderView();
    expect(await screen.findByText('1 in flight')).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
  });

  test('attaching a pipeline PUTs the new list', async () => {
    mockGets();
    axios.put.mockResolvedValue({ data: { ...ws, pipeline_ids: ['p1', 'p2'] } });
    renderView();
    fireEvent.click(await screen.findByTitle('Attach to this workspace'));
    await waitFor(() =>
      expect(axios.put).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/w1$/), { pipeline_ids: ['p1', 'p2'] })
    );
    await waitFor(() => expect(screen.getAllByTitle('Detach from this workspace')).toHaveLength(2));
  });

  test('detaching removes it; a failure is reported', async () => {
    mockGets();
    axios.put.mockRejectedValue({ response: { data: { message: 'Editing a workspace requires the editor or owner role' } } });
    renderView();
    fireEvent.click(await screen.findByTitle('Detach from this workspace'));
    await waitFor(() => expect(axios.put).toHaveBeenCalledWith(expect.any(String), { pipeline_ids: [] }));
    expect(await screen.findByText('Editing a workspace requires the editor or owner role')).toBeInTheDocument();
  });

  test('Statistics navigates for attached pipelines and is disabled otherwise', async () => {
    mockGets();
    renderView();
    await screen.findByText('Faces');
    const [attachedStats, availableStats] = screen.getAllByText('▤ Statistics').map((el) => el.closest('button'));
    expect(availableStats).toBeDisabled();
    fireEvent.click(attachedStats);
    expect(await screen.findByText('stats page')).toBeInTheDocument();
  });
});
