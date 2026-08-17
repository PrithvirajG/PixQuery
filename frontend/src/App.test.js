import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

// The CRA boilerplate test asserted a "learn react" link that no longer
// exists. PixQuery's App renders the LandingPage (marketing/auth screen)
// when there is no authenticated user, which is always the case in tests
// since there is no stored auth token and axios calls are unmocked here
// (AuthProvider skips the profile fetch entirely when there's no token).
test('renders the landing page when there is no authenticated user', () => {
  render(<App />);
  expect(screen.getByText('PixQuery')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /sign up free/i })).toBeInTheDocument();
});

test('opens the auth modal when "Sign Up Free" is clicked', () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /sign up free/i }));
  expect(screen.getByText('Create Account')).toBeInTheDocument();
});
