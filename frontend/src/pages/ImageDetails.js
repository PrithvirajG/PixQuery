import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography, Button } from '@mui/material';
import axios from 'axios';

// Utility: Generate consistent color from label
const getColorForLabel = (label) => {
  const hash = label.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const hue = hash % 360;
  return `hsl(${hue}, 70%, 60%)`;
};

function ImageDetails() {
  const { id } = useParams();
  const [imageData, setImageData] = useState(null);
  const [showDetections, setShowDetections] = useState(false);
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const [zoomLevel, setZoomLevel] = useState(1);

  const imageRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    axios
      .get(`http://localhost:8000/images/${id}`)
      .then((res) => {
        setImageData(res.data);
        console.log('Image data loaded:', res.data);
      })
      .catch((err) => console.error('Failed to load image', err));
  }, [id]);

  useEffect(() => {
    const updateSizes = () => {
      if (imageRef.current) {
        const newNaturalSize = {
          width: imageRef.current.naturalWidth,
          height: imageRef.current.naturalHeight,
        };
        setNaturalSize(newNaturalSize);
        console.log('Sizes updated:', { naturalSize: newNaturalSize });
      }
    };

    if (imageRef.current?.complete) updateSizes();
    const resizeObserver = new ResizeObserver(updateSizes);
    if (containerRef.current) resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, [imageData]);

  const handleImageLoad = () => {
    if (imageRef.current) {
      const newNaturalSize = {
        width: imageRef.current.naturalWidth,
        height: imageRef.current.naturalHeight,
      };
      setNaturalSize(newNaturalSize);
      console.log('Image loaded, natural size:', newNaturalSize);
    }
  };

  if (!imageData) return <Box sx={{ p: 2 }}>Loading...</Box>;

  const fileName = imageData.path.split('/').pop();
  let detections = [];
  if (imageData.detections) {
    try {
      detections = Array.isArray(imageData.detections)
        ? imageData.detections
        : JSON.parse(imageData.detections);
      console.log('Detections parsed:', detections);
    } catch (e) {
      console.error('Failed to parse detections string:', e);
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row', p: 3, gap: 3, height: '80vh' }}>
      {/* Analytics Column */}
      <Box sx={{ flex: 1, maxWidth: '300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Button
          variant="contained"
          onClick={() => setShowDetections(!showDetections)}
          sx={{ mb: 1, borderRadius: '50px' }}
        >
          {showDetections ? 'Hide Detections' : 'Show Detections'}
        </Button>
        <Button
          variant="outlined"
          onClick={() => setZoomLevel(zoomLevel + 0.1)}
          sx={{ mb: 1 }}
        >
          Zoom In
        </Button>
        <Button
          variant="outlined"
          onClick={() => setZoomLevel(Math.max(0.1, zoomLevel - 0.1))}
          sx={{ mb: 1 }}
        >
          Zoom Out
        </Button>
        <Box sx={{ mt: 2 }}>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            Description:
          </Typography>
          <Typography variant="body1">{imageData.description}</Typography>
        </Box>
      </Box>

      {/* Image Column */}
      <Box sx={{ flex: 2, position: 'relative', overflow: 'auto' }} ref={containerRef}>
        <Box
          sx={{
            transform: `scale(${zoomLevel})`,
            transformOrigin: 'top left',
            width: `${naturalSize.width}px`,
            height: `${naturalSize.height}px`,
          }}
        >
          <Box sx={{ position: 'relative', width: '100%', height: '100%' }}>
            <img
              src={`http://localhost:8000/images_source/${fileName}`}
              alt={imageData.description}
              ref={imageRef}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                display: 'block',
              }}
              onLoad={handleImageLoad}
            />
            {showDetections && naturalSize.width > 0 && (
              <Box
                sx={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  pointerEvents: 'none',
                }}
              >
                {detections.map((det, idx) => {
                  const [center_x, center_y, w, h] = det.bbox;
                  const x_min = center_x - w / 2;
                  const y_min = center_y - h / 2;
                  const left = (x_min / naturalSize.width) * 100;
                  const top = (y_min / naturalSize.height) * 100;
                  const width = (w / naturalSize.width) * 100;
                  const height = (h / naturalSize.height) * 100;
                  console.log('Detection box percentages:', { label: det.label, left, top, width, height });
                  const color = getColorForLabel(det.label);

                  return (
                    <Box
                      key={idx}
                      sx={{
                        position: 'absolute',
                        left: `${left}%`,
                        top: `${top}%`,
                        width: `${width}%`,
                        height: `${height}%`,
                        border: `2px solid ${color}`,
                        boxSizing: 'border-box',
                        backgroundColor: 'rgba(0, 0, 0, 0.25)',
                        color: '#fff',
                        fontSize: '12px',
                        padding: '2px 4px',
                      }}
                    >
                      {det.label} ({(det.confidence * 100).toFixed(1)}%)
                    </Box>
                  );
                })}
              </Box>
            )}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

export default ImageDetails;