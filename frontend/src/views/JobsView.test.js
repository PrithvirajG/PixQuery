import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import axios from 'axios';
import JobsView from './JobsView';

jest.mock('axios');

const overview = {
  total_images: 120,
  active_workspaces: 3,
  pipelines_defined: 2,
  jobs_completed: 100,
  jobs_failed: 5,
  jobs_processing: 1,
  jobs_queued: 2,
};

const jobs = [
  { _id: 'j1', asset_id: 'asset-aaaaaaaaaa', pipeline_id: 'p1', status: 'completed', updated_at: '2024-01-01T00:00:00Z', attempt_count: 1 },
  { _id: 'j2', asset_id: 'asset-bbbbbbbbbb', pipeline_id: 'p1', status: 'failed', updated_at: '2024-01-02T00:00:00Z', attempt_count: 3 },
];

describe('JobsView', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('shows a loading spinner while data is being fetched', () => {
    axios.get.mockReturnValue(new Promise(() => {})); // never resolves
    render(<JobsView />);
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  test('renders stat cards and the jobs table once loaded', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/stats/overview')) return Promise.resolve({ data: overview });
      if (url.includes('/stats/jobs/recent')) return Promise.resolve({ data: jobs });
      return Promise.reject(new Error('unexpected url ' + url));
    });

    render(<JobsView />);

    await waitFor(() => expect(screen.getByText('120')).toBeInTheDocument());
    expect(screen.getByText('Active Workspaces')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
  });

  test('shows the empty state when there are no jobs', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/stats/overview')) return Promise.resolve({ data: overview });
      if (url.includes('/stats/jobs/recent')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });

    render(<JobsView />);
    await waitFor(() => expect(screen.getByText('No jobs yet')).toBeInTheDocument());
  });

  test('shows an error banner when loading fails', async () => {
    axios.get.mockRejectedValue(new Error('network down'));
    render(<JobsView />);
    await waitFor(() => expect(screen.getByText('Failed to load statistics')).toBeInTheDocument());
  });

  test('clicking Requeue on a failed job calls the requeue endpoint and reloads', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/stats/overview')) return Promise.resolve({ data: overview });
      if (url.includes('/stats/jobs/recent')) return Promise.resolve({ data: jobs });
      return Promise.reject(new Error('unexpected url ' + url));
    });
    axios.post.mockResolvedValue({ data: {} });

    render(<JobsView />);
    await waitFor(() => expect(screen.getByText('failed')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Requeue'));

    await waitFor(() =>
      expect(axios.post).toHaveBeenCalledWith('http://localhost:8000/jobs/j2/requeue')
    );
  });
});
