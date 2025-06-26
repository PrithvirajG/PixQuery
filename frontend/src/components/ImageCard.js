import React, { useState } from 'react';
import { Card, CardMedia, Typography, CardActionArea, Box } from '@mui/material';
import { Link } from 'react-router-dom';

function ImageCard({ image, filepath }) {
  const fileName = filepath ? filepath.split('/').pop() : '';
  const [hovered, setHovered] = useState(false);

  // Handle detections safely
  let detections = [];
  let labels = [];
  if (image.detections) {
    // console.log('Image Detections:', image.detections);
    if (Array.isArray(image.detections)) {
      detections = image.detections;
      labels = detections.map(d => d.label || 'Unknown');
      // console.log('Parsed Detections:', detections);
      // console.log('Parsed Labels:', labels);
    } else if (typeof image.detections === 'string') {
      try {
        detections = JSON.parse(image.detections);
      } catch (e) {
        console.error('Failed to parse detections string:', e);
      }
    }
  }

  return (
    <Card
      sx={{
        borderRadius: 2,
        boxShadow: 3,
        transition: 'transform 0.2s',
        '&:hover': { transform: 'scale(1.05)', boxShadow: 6 },
        width: 300, // Fixed width
        height: 350, // Fixed total height
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden', // Prevent overflow
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <CardActionArea
        component={Link}
        to={`/image/${image.id}`}
        target="_blank"
        rel="noopener noreferrer"
        sx={{ flexGrow: 1, position: 'relative', overflow: 'hidden'}}
      >
        <CardMedia
          component="img"
          height="250" // Fixed image height
          image={`http://localhost:8000/images_source/${fileName}`}
          alt={image.description}
          sx={{ objectFit: 'cover', width: '100%', height: '80%' }} // Ensure uniform scaling
        />
        {hovered && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '250',
              bottom: '70px',
              backgroundColor: 'rgba(0, 0, 0, 0.7)',
              color: 'white',
              padding: 1,
              borderRadius: 2,
              overflowY: 'auto', // Enable vertical scroll
            }}
          >
            <Typography variant="body2" sx={{ 
              mb: 1 , 
              fontWeight: 'bold', 
              fontSize: 18 
              }}>
              Metadata:
            </Typography>
            <Typography variant="body2">
              <b>Description:</b> {image.description || 'Absent'}
            </Typography>
            <Typography variant="body2">
              <b>Score:</b> {Number(image.score).toFixed(3) || 'NA'}
            </Typography>
            <Typography variant="body2">
               <b>Detections:</b> {labels.join(', ') || 'NA'}
            </Typography>
          </Box>
        )}
        <Box sx={{ p: 1, height: 50, display: 'flex', alignItems: 'center' }}> {/* Fixed description height */}
          <Typography variant="body1" fontWeight="bold" fontSize={14}>
            {image.description || 'No description'}
          </Typography>
        </Box>
      </CardActionArea>
    </Card>
  );
}

export default ImageCard;