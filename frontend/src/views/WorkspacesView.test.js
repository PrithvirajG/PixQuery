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

// ── members modal + role-gated card actions ─────────────────────────────────

const ownerWs = { _id: 'w1', name: 'design-refs', workspace_path: '/p', active: true, pipeline_ids: ['p1'], my_role: 'owner' };
const members = [
  { user_id: 'u-owner', username: 'owner', role: 'owner' },
  { user_id: 'u-bob', username: 'bob', role: 'viewer' },
];

function mockApi({ ws = [ownerWs], memberList = members, search = [] } = {}) {
  axios.get.mockImplementation((url) => {
    if (url.endsWith('/members')) return Promise.resolve({ data: memberList });
    if (url.endsWith('/user-search')) return Promise.resolve({ data: search });
    if (url.endsWith('/workspaces')) return Promise.resolve({ data: ws });
    if (url.endsWith('/pipelines')) return Promise.resolve({ data: [] });
    return Promise.reject(new Error('unexpected url ' + url));
  });
}

async function openMembers() {
  fireEvent.click(await screen.findByTitle('Manage members'));
  return screen.findByText('bob');
}

describe('WorkspacesView members modal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.confirm.mockReturnValue(true);
  });

  test('owner sees invite box and per-member controls', async () => {
    mockApi();
    renderView();
    await openMembers();
    expect(screen.getByPlaceholderText('Start typing a username…')).toBeInTheDocument();
    expect(screen.getByTitle('Revoke access')).toBeInTheDocument();
  });

  test('viewer sees the list read-only', async () => {
    mockApi({ ws: [{ ...ownerWs, my_role: 'viewer' }] });
    renderView();
    await openMembers();
    expect(screen.queryByPlaceholderText('Start typing a username…')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Revoke access')).not.toBeInTheDocument();
  });

  test('typing searches (debounced) and picking a suggestion adds with the chosen role', async () => {
    mockApi({ search: [{ user_id: 'u-carol', username: 'carol' }] });
    axios.post.mockResolvedValue({ data: [...members, { user_id: 'u-carol', username: 'carol', role: 'editor' }] });
    renderView();
    await openMembers();

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'editor' } });
    fireEvent.change(screen.getByPlaceholderText('Start typing a username…'), { target: { value: 'ca' } });

    await waitFor(() =>
      expect(axios.get).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/w1\/user-search$/), { params: { q: 'ca' } })
    );
    fireEvent.click(await screen.findByText('add as editor'));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/w1\/members$/), { username: 'carol', role: 'editor' });
      expect(screen.getByText('carol')).toBeInTheDocument();
    });
  });

  test('no matches shows a hint', async () => {
    mockApi({ search: [] });
    renderView();
    await openMembers();
    fireEvent.change(screen.getByPlaceholderText('Start typing a username…'), { target: { value: 'zz' } });
    expect(await screen.findByText('No matching users')).toBeInTheDocument();
  });

  test('add failure shows the backend message', async () => {
    mockApi({ search: [{ user_id: 'u-carol', username: 'carol' }] });
    axios.post.mockRejectedValue({ response: { data: { message: 'No user named carol' } } });
    renderView();
    await openMembers();
    fireEvent.change(screen.getByPlaceholderText('Start typing a username…'), { target: { value: 'ca' } });
    fireEvent.click(await screen.findByText('add as viewer'));
    expect(await screen.findByText('No user named carol')).toBeInTheDocument();
  });

  test('changing a role PATCHes and revoking DELETEs', async () => {
    mockApi();
    axios.patch.mockResolvedValue({ data: [members[0], { ...members[1], role: 'editor' }] });
    axios.delete.mockResolvedValue({ data: [members[0]] });
    renderView();
    await openMembers();

    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'editor' } });
    await waitFor(() =>
      expect(axios.patch).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/w1\/members\/u-bob$/), { role: 'editor' })
    );

    fireEvent.click(screen.getByTitle('Revoke access'));
    await waitFor(() => expect(axios.delete).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/w1\/members\/u-bob$/)));
    await waitFor(() => expect(screen.queryByText('bob')).not.toBeInTheDocument());
  });
});

describe('WorkspacesView card actions by role', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.confirm.mockReturnValue(true);
  });

  test('viewer: no edit/delete, scan disabled with a reason', async () => {
    mockApi({ ws: [{ ...ownerWs, my_role: 'viewer' }] });
    renderView();
    await screen.findByText('design-refs');
    expect(screen.queryByTitle('Edit workspace')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Delete workspace')).not.toBeInTheDocument();
    expect(screen.getByTitle('Viewers cannot trigger scans')).toBeDisabled();
  });

  test('editor: can edit but not delete', async () => {
    mockApi({ ws: [{ ...ownerWs, my_role: 'editor' }] });
    renderView();
    await screen.findByText('design-refs');
    expect(screen.getByTitle('Edit workspace')).toBeInTheDocument();
    expect(screen.queryByTitle('Delete workspace')).not.toBeInTheDocument();
  });

  test('scan disabled without pipelines', async () => {
    mockApi({ ws: [{ ...ownerWs, pipeline_ids: [] }] });
    renderView();
    expect(await screen.findByTitle('Attach at least one pipeline before scanning')).toBeDisabled();
  });

  test('scan posts, and a failure is shown', async () => {
    mockApi();
    axios.post.mockRejectedValueOnce({ response: { data: { message: 'Broker unavailable' } } });
    renderView();
    fireEvent.click(await screen.findByTitle('Trigger an immediate scan of this folder'));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/w1\/scan$/)));
    expect(await screen.findByText('Broker unavailable')).toBeInTheDocument();
  });

  test('delete asks for confirmation', async () => {
    mockApi();
    axios.delete.mockResolvedValue({});
    renderView();
    window.confirm.mockReturnValueOnce(false);
    fireEvent.click(await screen.findByTitle('Delete workspace'));
    expect(axios.delete).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTitle('Delete workspace'));
    await waitFor(() => expect(axios.delete).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/w1$/)));
  });
});
