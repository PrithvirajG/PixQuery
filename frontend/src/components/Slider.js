import { useState } from 'react';
import { Box, Slider as MUISlider, Typography } from '@mui/material';

function Slider({ min, max, step, value, name, onSlide }) {
  const [sliderValue, setSliderValue] = useState(value);

  const handleChange = (event, newValue) => {
    setSliderValue(newValue);
    onSlide(newValue);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        border: '2px solid #decaf8',
        borderRadius: '50px',
        backgroundColor: '#fff', // optional for contrast in dark theme
      }}
    >
      <Typography 
        variant="body2" 
        color="text.primary" 
        sx={{ 
          paddingLeft: 2,
          paddingRight: 0.5,
          whiteSpace: 'nowrap', 
          fontSize: '15px', // 14px
          fontFamily: 'Roboto, sans-serif', // Ensure consistent font
          fontWeight: 'bold', // Make the label bold
          }}>
        {name}
      </Typography>

      <MUISlider
        min={min}
        max={max}
        step={step}
        value={sliderValue}
        onChange={handleChange}
        aria-label={name}
        sx={{ flex: 1 }}
      />

      <Typography variant="body2" color="text.primary" 
      sx={{ 
        paddingRight: 2,
        paddingLeft: 0.5,
        whiteSpace: 'nowrap' }}>
        {sliderValue}
      </Typography>
    </Box>
  );
}

export default Slider;
