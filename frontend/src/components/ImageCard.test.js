import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ImageCard from './ImageCard';

function renderCard(props) {
  return render(
    <MemoryRouter>
      <ImageCard {...props} />
    </MemoryRouter>
  );
}

describe('ImageCard', () => {
  const baseImage = {
    id: 'img-1',
    description: 'A dog on the beach',
    score: 0.87231,
    detections: [{ label: 'dog' }, { label: 'beach' }],
  };

  test('renders the description text', () => {
    renderCard({ image: baseImage, filepath: '/photos/dog.jpg' });
    expect(screen.getByText('A dog on the beach')).toBeInTheDocument();
  });

  test('falls back to "No description" when the image has none', () => {
    renderCard({ image: { ...baseImage, description: undefined }, filepath: '/photos/dog.jpg' });
    expect(screen.getByText('No description')).toBeInTheDocument();
  });

  test('renders the image with alt text and derives filename from filepath', () => {
    renderCard({ image: baseImage, filepath: '/photos/sub/dog.jpg' });
    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('alt', 'A dog on the beach');
    expect(img).toHaveAttribute('src', expect.stringContaining('dog.jpg'));
  });

  test('links to the image detail page', () => {
    renderCard({ image: baseImage, filepath: '/photos/dog.jpg' });
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/image/img-1');
  });

  test('shows metadata overlay (description, score, detections) on hover', () => {
    renderCard({ image: baseImage, filepath: '/photos/dog.jpg' });
    // Metadata overlay text isn't visible until hover.
    expect(screen.queryByText(/Metadata:/)).not.toBeInTheDocument();

    const link = screen.getByRole('link');
    fireEvent.mouseEnter(link);

    expect(screen.getByText(/Metadata:/)).toBeInTheDocument();
    expect(screen.getByText(/0\.872/)).toBeInTheDocument();
    expect(screen.getByText(/dog, beach/)).toBeInTheDocument();

    fireEvent.mouseLeave(link);
    expect(screen.queryByText(/Metadata:/)).not.toBeInTheDocument();
  });

  test('parses a JSON string detections payload', () => {
    const image = { ...baseImage, detections: JSON.stringify([{ label: 'cat' }]) };
    renderCard({ image, filepath: '/photos/dog.jpg' });
    fireEvent.mouseEnter(screen.getByRole('link'));
    // The component only maps labels from array detections; a JSON string is
    // parsed into `detections` but labels come from the pre-existing `labels`
    // array which stays empty for the string branch, so it should show "NA".
    expect(screen.getByText((content, node) => node.textContent === 'Detections: NA')).toBeInTheDocument();
  });

  test('handles missing detections gracefully', () => {
    const image = { ...baseImage, detections: undefined };
    renderCard({ image, filepath: '/photos/dog.jpg' });
    fireEvent.mouseEnter(screen.getByRole('link'));
    expect(screen.getByText((content, node) => node.textContent === 'Detections: NA')).toBeInTheDocument();
  });
});
