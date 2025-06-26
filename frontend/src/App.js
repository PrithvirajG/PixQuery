import React from 'react';
import { BrowserRouter as Router, Route, Routes, Link } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import theme from './theme';
import ImageQueryView from './views/ImageQueryView';
import ModelManagementView from './views/ModelManagementView';
import ImageUploadView from './views/ImageUploadView';
import ImageDetails from './pages/ImageDetails'; // Import ImageDetails
import ProgressTrackingView from './views/ProgressTrackingView';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <Router>
        <AppBar position="static" color="primary">
          <Toolbar>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              PixQuery
            </Typography>
            <Button color="inherit" component={Link} to="/">Image Query</Button>
            <Button color="inherit" component={Link} to="/model-management">Model Management</Button>
            <Button color="inherit" component={Link} to="/image-upload">Image Upload</Button>
            <Button color="inherit" component={Link} to="/progress-tracking">Progress Tracking</Button>
          </Toolbar>
        </AppBar>
        <Routes>
          <Route path="/" element={<ImageQueryView />} />
          <Route path="/model-management" element={<ModelManagementView />} />
          <Route path="/image-upload" element={<ImageUploadView />} />
          <Route path="/progress-tracking" element={<ProgressTrackingView />} />
          <Route path="/image/:id" element={<ImageDetails />} /> {/* Add this route */}
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;