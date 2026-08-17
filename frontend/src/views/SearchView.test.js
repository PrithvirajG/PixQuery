import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import SearchView from './SearchView';

jest.mock('axios');

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

function renderView() {
  return render(
    <MemoryRouter>
      <SearchView />
    </MemoryRouter>
  );
}

describe('SearchView', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('loads workspaces and an initial empty result set on mount', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: [] });
      if (url.includes('/search')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });

    renderView();

    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/workspaces'));
    await waitFor(() => expect(screen.getByText(/No images found/i)).toBeInTheDocument());
  });

  test('renders search results returned from the API', async () => {
    const results = [
      { _id: 'a1', current_path: '/photos/dog.jpg', match_reason: { fields: ['caption'], similarity: 0.9 } },
      { _id: 'a2', current_path: '/photos/cat.jpg' },
    ];
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: [] });
      if (url.startsWith('http://localhost:8000/search')) return Promise.resolve({ data: results });
      return Promise.reject(new Error('unexpected url ' + url));
    });

    renderView();

    await waitFor(() => expect(screen.getAllByTitle(/dog\.jpg|cat\.jpg/).length).toBe(2));
  });

  test('shows an error message when the search request fails', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: [] });
      if (url.startsWith('http://localhost:8000/search')) return Promise.reject(new Error('boom'));
      return Promise.reject(new Error('unexpected url ' + url));
    });

    renderView();

    await waitFor(() => expect(screen.getByText(/Search failed\. Please try again\./i)).toBeInTheDocument());
  });

  test('typing a query and submitting triggers a new search request', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: [] });
      if (url.startsWith('http://localhost:8000/search')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });

    renderView();
    await waitFor(() => expect(screen.getByText(/No images found/i)).toBeInTheDocument());

    const input = screen.getByPlaceholderText(/search your library/i);
    fireEvent.change(input, { target: { value: 'sunset' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() =>
      expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('query=sunset'))
    );
  });

  test('switching search mode triggers a re-fetch with the new mode', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/workspaces')) return Promise.resolve({ data: [] });
      if (url.startsWith('http://localhost:8000/search')) return Promise.resolve({ data: [] });
      return Promise.reject(new Error('unexpected url ' + url));
    });

    renderView();
    await waitFor(() => expect(screen.getByText(/No images found/i)).toBeInTheDocument());

    fireEvent.click(screen.getByText('Semantic'));

    await waitFor(() =>
      expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('mode=semantic'))
    );
  });
});
