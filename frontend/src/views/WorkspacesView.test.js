import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import WorkspacesView from './WorkspacesView';

jest.mock('axios');

// window.confirm is used before deletes.
window.confirm = jest.fn(() => true);

function renderView() {
  return render(
    <MemoryRouter>
      <WorkspacesView />
    </MemoryRouter>
  );
}

const workspaces = [
  { _id: 'w1', name: 'design-refs', workspace_path: '/photos/design', active: true, pipeline_ids: [], my_role: 'owner' },
  { _id: 'w2', name: 'family', workspace_path: '/photos/family', active: false, pipeline_ids: [], my_role: 'viewer' },
];

describe('WorkspacesView', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.confirm.mockReturnValue(true);
  });

  test('shows a loading indicator before data arrives', () => {
    axios.get.mockReturnValue(new Promise(() => {}));
    renderView();
    expect(screen.getByText('loading…')).toBeInTheDocument();
  });

  test('renders the empty state when there are no workspaces', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: [] });
      if (url.includes('/pipelines')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });
    renderView();
    await waitFor(() => expect(screen.getByText('No workspaces yet')).toBeInTheDocument());
  });

  test('renders workspace cards once loaded', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: workspaces });
      if (url.includes('/pipelines')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });
    renderView();
    await waitFor(() => expect(screen.getByText('design-refs')).toBeInTheDocument());
    expect(screen.getByText('family')).toBeInTheDocument();
    expect(screen.getByText('2 spaces')).toBeInTheDocument();
  });

  test('filters workspaces by name', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: workspaces });
      if (url.includes('/pipelines')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });
    renderView();
    await waitFor(() => expect(screen.getByText('design-refs')).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText('Filter workspaces'), { target: { value: 'family' } });

    expect(screen.queryByText('design-refs')).not.toBeInTheDocument();
    expect(screen.getByText('family')).toBeInTheDocument();
  });

  test('shows an error banner when loading fails', async () => {
    axios.get.mockRejectedValue(new Error('network error'));
    renderView();
    await waitFor(() => expect(screen.getByText('Failed to load workspaces')).toBeInTheDocument());
  });

  test('opens the "New workspace" drawer', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: [] });
      if (url.includes('/pipelines')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });
    renderView();
    await waitFor(() => expect(screen.getAllByText('+ New workspace').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('+ New workspace')[0]);

    expect(screen.getByText('a watched folder and its processing pipelines')).toBeInTheDocument();
  });
});
