import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import PipelineStatsView from './PipelineStatsView';

jest.mock('axios');

const API = 'http://localhost:8000';
const WS = 'ws-1';
const PL = 'pl-1';

const workspace = { _id: WS, name: 'Test 1 a', my_role: 'owner' };
const pipeline = { _id: PL, name: 'Test Pipeline', nodes: [{ node_id: 'n0' }] };

const jobs = [
  { _id: 'j1', workspace_id: WS, pipeline_id: PL, asset_id: 'a1', status: 'completed', updated_at: '2026-01-01T00:00:00Z' },
  { _id: 'j2', workspace_id: WS, pipeline_id: PL, asset_id: 'a2', status: 'failed', updated_at: '2026-01-02T00:00:00Z', attempt_count: 3, last_error: { message: 'boom' } },
  // Belongs to another pipeline — must be filtered out of this view.
  { _id: 'j3', workspace_id: WS, pipeline_id: 'other', asset_id: 'a3', status: 'completed', updated_at: '2026-01-03T00:00:00Z' },
];

function mockGets(jobList = jobs) {
  axios.get.mockImplementation((url) => {
    if (url.includes(`/workspaces/${WS}`)) return Promise.resolve({ data: workspace });
    if (url.includes(`/pipelines/${PL}`)) return Promise.resolve({ data: pipeline });
    if (url.includes('/stats/jobs/recent')) return Promise.resolve({ data: jobList });
    return Promise.reject(new Error('unexpected url ' + url));
  });
}

function renderView() {
  return render(
    <MemoryRouter initialEntries={[`/workspaces/${WS}/pipelines/${PL}/stats`]}>
      <Routes>
        <Route
          path="/workspaces/:id/pipelines/:pipelineId/stats"
          element={<PipelineStatsView />}
        />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(window, 'confirm').mockReturnValue(true);
});

afterEach(() => {
  window.confirm.mockRestore();
});

describe('PipelineStatsView', () => {
  test('counts only this pipeline’s jobs', async () => {
    mockGets();
    renderView();

    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());
    // 2 of the 3 jobs belong to this pipeline; 1 completed, 1 failed.
    expect(screen.getByText('of 2')).toBeInTheDocument();
  });

  test('Clear outputs asks for confirmation and calls the delete endpoint', async () => {
    mockGets();
    axios.delete.mockResolvedValue({ data: { outputs_deleted: 4, runs_deleted: 2, jobs_deleted: 2 } });

    renderView();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Clear outputs/ }));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() =>
      expect(axios.delete).toHaveBeenCalledWith(
        `${API}/workspaces/${WS}/pipelines/${PL}/outputs`
      )
    );
  });

  test('cancelling the confirmation does not call the endpoint', async () => {
    window.confirm.mockReturnValue(false);
    mockGets();

    renderView();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Clear outputs/ }));

    expect(window.confirm).toHaveBeenCalled();
    expect(axios.delete).not.toHaveBeenCalled();
  });

  test('Clear outputs is disabled when the pipeline has no jobs here', async () => {
    mockGets([]);
    renderView();

    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Clear outputs/ })).toBeDisabled();
  });

  test('surfaces an error if clearing fails', async () => {
    mockGets();
    axios.delete.mockRejectedValue(new Error('nope'));

    renderView();
    await waitFor(() => expect(screen.getByText('Test Pipeline')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Clear outputs/ }));

    await waitFor(() =>
      expect(screen.getByText('Failed to clear outputs')).toBeInTheDocument()
    );
  });
});
