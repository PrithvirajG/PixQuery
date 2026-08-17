import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AppShell from './AppShell';
import { useAuth } from '../context/AuthContext';

jest.mock('../context/AuthContext', () => ({
  useAuth: jest.fn(),
}));

function renderShell(initialPath = '/search') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AppShell>
        <div>content</div>
      </AppShell>
    </MemoryRouter>
  );
}

describe('AppShell', () => {
  beforeEach(() => {
    useAuth.mockReturnValue({ user: { username: 'alice' }, logout: jest.fn() });
  });

  test('renders the nav items for Search, Spaces, and Pipelines', () => {
    renderShell();
    expect(screen.getByTitle('Search')).toBeInTheDocument();
    expect(screen.getByTitle('Spaces')).toBeInTheDocument();
    expect(screen.getByTitle('Pipelines')).toBeInTheDocument();
  });

  test('renders the children content area', () => {
    renderShell();
    expect(screen.getByText('content')).toBeInTheDocument();
  });

  test("shows the user's initials in the avatar button", () => {
    renderShell();
    expect(screen.getByTitle('alice')).toHaveTextContent('AL');
  });

  test('opens the sign-out menu and calls logout when clicked', () => {
    const logout = jest.fn();
    useAuth.mockReturnValue({ user: { username: 'alice' }, logout });
    renderShell();

    expect(screen.queryByText('Sign out')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTitle('alice'));
    expect(screen.getByText('Sign out')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Sign out'));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  test('falls back to "?" avatar text when there is no user', () => {
    useAuth.mockReturnValue({ user: null, logout: jest.fn() });
    renderShell();
    // title attribute becomes undefined -> query by text content instead
    expect(screen.getByText('?')).toBeInTheDocument();
  });
});
