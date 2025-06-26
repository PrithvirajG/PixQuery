import React from 'react';
import { Box, Container, Typography } from '@mui/material';

function ImageUploadView() {
  return (
    <Container maxWidth="lg" sx={{ height: 'calc(100vh - 64px)', display: 'flex', justifyContent: 'center', alignItems: 'center', backgroundColor: 'background.paper' }}>
      <Typography variant="h5">Image Upload (Coming Soon)</Typography>
    </Container>
  );
}

export default ImageUploadView;