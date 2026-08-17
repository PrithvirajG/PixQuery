import { useState } from 'react';
import { Box, TextField, Button } from '@mui/material';

function SearchBar({ onSearch }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(query);
  };

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        display: 'flex',
        alignItems: 'center',
        // gap: 1,
        gap: 2,
        border: '2px solid #decaf8',
        paddingBottom: 0,
        paddingTop: 0,
        // border: '1px solid #decaf8',
        borderRadius: '50px',
        backgroundColor: '#fff', // optional: theme.palette.background.paper
      }}
    >
      <TextField
        placeholder="Search images (e.g., cat in a tree)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        sx={{
          width: '80%',
        }}
      />
      <Button 
        type="submit" 
        variant="contained" 
        color="primary"
        sx={{
          width: '20%',
        }}
      
      >
        Search
      </Button>
    </Box>
  );
}

export default SearchBar;
