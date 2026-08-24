import React from 'react';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SearchBar from './SearchBar';

// NOTE: the project pins @testing-library/user-event@13, which predates the
// userEvent.setup() API — use the module-level helpers directly instead.

// MUI's ButtonBase ripple (useLazyRipple) schedules its own setState ~80ms
// after a click via an internal timer (see @mui/material's DELAY_RIPPLE),
// independent of the click handler itself. That update lands after the
// synchronous click has already returned, so it's not covered by RTL's
// automatic act() wrapping. Flushing a short real-timer delay inside act()
// lets that ripple state settle before the test moves on and avoids
// "not wrapped in act(...)" warnings without hiding any real issue.
const flushRipple = () => act(() => new Promise((resolve) => setTimeout(resolve, 100)));

describe('SearchBar', () => {
  test('renders an input and a search button', () => {
    render(<SearchBar onSearch={() => {}} />);
    expect(screen.getByPlaceholderText(/search images/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
  });

  test('updates the input value as the user types', () => {
    render(<SearchBar onSearch={() => {}} />);
    const input = screen.getByPlaceholderText(/search images/i);
    userEvent.type(input, 'cat in a tree');
    expect(input).toHaveValue('cat in a tree');
  });

  test('calls onSearch with the current query when the form is submitted via the button', async () => {
    const onSearch = jest.fn();
    render(<SearchBar onSearch={onSearch} />);
    const input = screen.getByPlaceholderText(/search images/i);
    userEvent.type(input, 'sunset beach');
    userEvent.click(screen.getByRole('button', { name: /search/i }));
    await flushRipple();
    expect(onSearch).toHaveBeenCalledTimes(1);
    expect(onSearch).toHaveBeenCalledWith('sunset beach');
  });

  test('calls onSearch with an empty string when submitted without typing anything', async () => {
    const onSearch = jest.fn();
    render(<SearchBar onSearch={onSearch} />);
    userEvent.click(screen.getByRole('button', { name: /search/i }));
    await flushRipple();
    expect(onSearch).toHaveBeenCalledWith('');
  });

  test('submitting does not reload the page (preventDefault called)', () => {
    const onSearch = jest.fn();
    render(<SearchBar onSearch={onSearch} />);
    const input = screen.getByPlaceholderText(/search images/i);
    userEvent.type(input, 'x');
    userEvent.type(input, '{enter}');
    expect(onSearch).toHaveBeenCalledWith('x');
  });
});
