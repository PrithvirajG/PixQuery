import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import axios from 'axios';
import { AuthProvider, useAuth } from './AuthContext';

jest.mock('axios');

function TestConsumer() {
  const { token, user, loading, login, register, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="token">{token ?? 'none'}</span>
      <span data-testid="user">{user?.username ?? 'none'}</span>
      <button onClick={() => login('bob', 'password123')}>login</button>
      <button onClick={() => register('bob', 'password123')}>register</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
    axios.interceptors = { request: { use: jest.fn(() => 1), eject: jest.fn() } };
  });

  test('useAuth throws when used outside an AuthProvider', () => {
    // Suppress the expected React error boundary console.error noise.
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    function Bare() {
      useAuth();
      return null;
    }
    expect(() => render(<Bare />)).toThrow('useAuth must be used within an AuthProvider');
    spy.mockRestore();
  });

  test('starts with loading=false and no user when there is no stored token', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    expect(screen.getByTestId('token')).toHaveTextContent('none');
    expect(screen.getByTestId('user')).toHaveTextContent('none');
  });

  test('fetches the user profile when a token is already in localStorage', async () => {
    localStorage.setItem('pixquery_token', 'stored-token');
    axios.get.mockResolvedValueOnce({ data: { username: 'carol' } });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('carol'));
    expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/auth/me');
    expect(screen.getByTestId('loading')).toHaveTextContent('false');
  });

  test('logs out automatically when session verification fails', async () => {
    localStorage.setItem('pixquery_token', 'bad-token');
    axios.get.mockRejectedValueOnce(new Error('401'));
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('token')).toHaveTextContent('none'));
    expect(localStorage.getItem('pixquery_token')).toBeNull();
    spy.mockRestore();
  });

  test('login stores the token and updates auth state on success', async () => {
    axios.post.mockResolvedValueOnce({ data: { access_token: 'new-token' } });
    axios.get.mockResolvedValueOnce({ data: { username: 'bob' } });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));

    await act(async () => {
      screen.getByText('login').click();
    });

    await waitFor(() => expect(screen.getByTestId('token')).toHaveTextContent('new-token'));
    expect(localStorage.getItem('pixquery_token')).toBe('new-token');
    expect(axios.post).toHaveBeenCalledWith('http://localhost:8000/auth/login', {
      username: 'bob',
      password: 'password123',
    });
  });

  test('login rethrows and leaves state unchanged on failure', async () => {
    const err = new Error('bad credentials');
    axios.post.mockRejectedValueOnce(err);
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});

    let caught;
    function Consumer() {
      const { login } = useAuth();
      return (
        <button
          onClick={async () => {
            try {
              await login('bob', 'wrongpass');
            } catch (e) {
              caught = e;
            }
          }}
        >
          try-login
        </button>
      );
    }

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await act(async () => {
      screen.getByText('try-login').click();
    });

    expect(caught).toBe(err);
    expect(localStorage.getItem('pixquery_token')).toBeNull();
    spy.mockRestore();
  });

  test('register calls the register endpoint then logs in', async () => {
    axios.post.mockResolvedValueOnce({ data: {} }); // register
    axios.post.mockResolvedValueOnce({ data: { access_token: 'reg-token' } }); // login
    axios.get.mockResolvedValueOnce({ data: { username: 'bob' } });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));

    await act(async () => {
      screen.getByText('register').click();
    });

    await waitFor(() => expect(screen.getByTestId('token')).toHaveTextContent('reg-token'));
    expect(axios.post).toHaveBeenNthCalledWith(1, 'http://localhost:8000/auth/register', {
      username: 'bob',
      password: 'password123',
    });
  });

  test('logout clears token, user, and localStorage', async () => {
    localStorage.setItem('pixquery_token', 'stored-token');
    axios.get.mockResolvedValueOnce({ data: { username: 'carol' } });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('carol'));

    act(() => {
      screen.getByText('logout').click();
    });

    expect(screen.getByTestId('token')).toHaveTextContent('none');
    expect(screen.getByTestId('user')).toHaveTextContent('none');
    expect(localStorage.getItem('pixquery_token')).toBeNull();
  });
});
