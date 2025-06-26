import React, { useState } from 'react';
import { Box, Container, Typography, Grid, Select, MenuItem } from '@mui/material';
import SearchBar from '../components/SearchBar';
import Slider from '../components/Slider';
import ImageCard from '../components/ImageCard';
import axios from 'axios';

function ImageQueryView() {
  const [results, setResults] = useState([]);
  const [sliderValue, setSliderValue] = useState(0.5);

  const onSlide = (value) => {
    setSliderValue(value);
    console.log('Slider value changed:', value);
  };

  const handleSearch = async (query) => {
    try {
      const res = await axios.get(`http://localhost:8000/search_descriptions?query=${encodeURIComponent(query)}`);
      console.log('Received Response:', res.data);
      setResults(res.data);
    } catch (err) {
      console.error('Search failed', err);
    }
  };

  return (
    <Container maxWidth="xlg" sx={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column', padding: 2 }}>
      <Box sx={{ height: '20%', display: 'flex', flexDirection: 'column', gap: 2, overflowY: 'auto', padding: 2, backgroundColor: 'background.paper', borderRadius: 2 }}>
        <Typography variant="h5" align="center">Image Query</Typography>
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 2, justifyContent: 'center' }}>
          <Box sx={{ flex: 1, minWidth: 200 }}>
            <SearchBar onSearch={handleSearch} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 200 }}>
            <Slider min={0} max={1} step={0.01} value={sliderValue} onSlide={onSlide} name="Score Threshold" />
          </Box>
          {/* <Box sx={{ width: 200 }}>
            <Select fullWidth variant="outlined">
              <MenuItem value="option1">Filter Option 1</MenuItem>
              <MenuItem value="option2">Filter Option 2</MenuItem>
            </Select>
          </Box> */}
        </Box>
      </Box>
      <Box sx={{ height: '80%', overflowY: 'auto', padding: 2 }}>
        <Grid container spacing={2}>
          {results
            .filter((img) => img.score >= sliderValue)
            .map((img) => (
              <Grid item xs={12} sm={6} md={4} key={img.id}>
                <ImageCard image={img} filepath={img.path} />
              </Grid>
            ))}
        </Grid>
      </Box>
    </Container>
  );
}

export default ImageQueryView;