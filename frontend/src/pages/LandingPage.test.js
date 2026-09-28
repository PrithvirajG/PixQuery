import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LandingPage from './LandingPage';
import { useAuth } from '../context/AuthContext';

jest.mock('../context/AuthContext', () => ({ useAuth: jest.fn() }));

const login = jest.fn();
const register = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  useAuth.mockReturnValue({ login, register });
});

function openAuth(buttonName) {
  const utils = render(<LandingPage />);
  fireEvent.click(screen.getAllByRole('button', { name: buttonName })[0]);
  return utils;
}

function fill({ username, password, confirm }) {
  if (username !== undefined)
    fireEvent.change(screen.getByPlaceholderText('Enter your username'), { target: { value: username } });
  const pw = screen.getAllByPlaceholderText('••••••••');
  if (password !== undefined) fireEvent.change(pw[0], { target: { value: password } });
  if (confirm !== undefined) fireEvent.change(pw[1], { target: { value: confirm } });
}

const submit = (container) => fireEvent.submit(container.querySelector('form'));

describe('LandingPage auth form', () => {
  test.each([
    [{}, /Please fill in all fields\.$/],
    [{ username: 'ab', password: 'secret1' }, /Username must be at least 3 characters\.$/],
    [{ username: 'alice', password: '123' }, /Password must be at least 6 characters\.$/],
  ])('validates %j before calling the API', (values, message) => {
    const { container } = openAuth('Login');
    fill(values);
    submit(container);
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  test('successful login calls login() and closes the modal', async () => {
    login.mockResolvedValue(true);
    const { container } = openAuth('Login');
    fill({ username: 'alice', password: 'secret1' });
    submit(container);
    await waitFor(() => expect(login).toHaveBeenCalledWith('alice', 'secret1'));
    await waitFor(() => expect(container.querySelector('form')).toBeNull());
  });

  test('failed login shows the backend message', async () => {
    login.mockRejectedValue({ response: { data: { error: true, message: 'Invalid username or password' } } });
    const { container } = openAuth('Login');
    fill({ username: 'alice', password: 'secret1' });
    submit(container);
    expect(await screen.findByText(/Invalid username or password/)).toBeInTheDocument();
    expect(container.querySelector('form')).not.toBeNull();
  });

  test('register rejects mismatched passwords without calling the API', () => {
    const { container } = openAuth('Sign Up Free');
    fill({ username: 'alice', password: 'secret1', confirm: 'secret2' });
    submit(container);
    expect(screen.getByText(/Passwords do not match\.$/)).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  test('successful register calls register()', async () => {
    register.mockResolvedValue(true);
    const { container } = openAuth('Sign Up Free');
    fill({ username: 'alice', password: 'secret1', confirm: 'secret1' });
    submit(container);
    await waitFor(() => expect(register).toHaveBeenCalledWith('alice', 'secret1'));
  });

  test('toggling views swaps login ⇄ register and clears the form', () => {
    openAuth('Login');
    fill({ username: 'alice' });
    expect(screen.queryByText('Confirm Password')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }));
    expect(screen.getByText('Confirm Password')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your username').value).toBe('');
    fireEvent.click(screen.getByRole('button', { name: 'Log In' }));
    expect(screen.queryByText('Confirm Password')).not.toBeInTheDocument();
  });
});
