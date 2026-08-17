import React from 'react';
import { render, screen, act } from '@testing-library/react';
import Slider from './Slider';

describe('Slider', () => {
  test('renders the label and the initial value', () => {
    render(<Slider min={0} max={100} step={1} value={40} name="Confidence" onSlide={() => {}} />);
    expect(screen.getByText('Confidence')).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
  });

  test('renders an MUI slider with the correct min/max and aria-label', () => {
    render(<Slider min={0} max={1} step={0.05} value={0.5} name="Threshold" onSlide={() => {}} />);
    const slider = screen.getByRole('slider', { name: 'Threshold' });
    expect(slider).toHaveAttribute('aria-valuemin', '0');
    expect(slider).toHaveAttribute('aria-valuemax', '1');
    expect(slider).toHaveAttribute('aria-valuenow', '0.5');
  });

  test('calls onSlide with the new value and updates the displayed value on change', async () => {
    const onSlide = jest.fn();
    render(<Slider min={0} max={100} step={1} value={10} name="Level" onSlide={onSlide} />);
    const slider = screen.getByRole('slider', { name: 'Level' });

    // MUI sliders respond to arrow-key presses on the focused thumb.
    act(() => {
      slider.focus();
      // eslint-disable-next-line testing-library/no-node-access
      slider.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    });

    expect(onSlide).toHaveBeenCalled();
    expect(screen.getByText('11')).toBeInTheDocument();

    // Focusing/moving the thumb also starts the underlying ButtonBase
    // ripple (useLazyRipple), which schedules its own setState on an
    // internal timer independent of the keydown handler above. Flush that
    // pending update inside act() so it doesn't leak an
    // "not wrapped in act(...)" warning into a later test.
    // eslint-disable-next-line testing-library/no-unnecessary-act
    await act(() => new Promise((resolve) => setTimeout(resolve, 100)));
  });
});
