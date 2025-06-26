import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1c0a32',
    },
    secondary: {
      main: '#1c0a32',
    },
    background: {
      default: '#1c0a32',
      paper: '#decaf8',
    },
    text: {
      primary: '#1c0a32',
      secondary: '#1c0a32',
    },
  },
  typography: {
    h5: {
      fontWeight: 600,
      color: '#decaf8',
    },
    body2: {
      color: '#decaf8',
    },
  },
  components: {
     MuiSlider: {
    styleOverrides: {
      root: {
        color: '#decaf8', // Thumb & track color
        height: '56px',
        paddingTop: 0,
        paddingBottom: 0,
        paddingLeft: 10,
        paddingRight: 10,
        // padding: '0px 0',
      },
      thumb: {
        height: 24,
        width: 24,
        backgroundColor: '#decaf8',
        border: '2px solid #1c0a32',
        // marginTop: -8,
        // marginLeft: -12,
        '&:hover, &.Mui-focusVisible': {
          boxShadow: '0px 0px 0px 6px rgba(47, 12, 90, 0.76)',
        },
      },
      track: {
        height: 8,
        borderRadius: 4,
      },
      rail: {
        height: 8,
        borderRadius: 4,
        opacity: 0.3,
        backgroundColor: '#decaf8',
      },
      valueLabel: {
        backgroundColor: '#decaf8',
        color: '#1c0a32',
        borderRadius: 8,
      },
    },
  },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 50,
          textTransform: 'none',
          // paddingTop: 12,
          // paddingBottom: 12,
          fontSize: '1rem',
          height: '56px', // Match default TextField height
          paddingLeft: 12,
          paddingRight: 12,

        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 50,
          backgroundColor: '#fff', // optional: adjust for contrast with dark mode
          height: '56px',
        },

        input: {
        // padding: '12px 14px', // Standard padding for vertical centering
      },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined',
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)',
        },
      },
    },
  },
});

export default theme;
