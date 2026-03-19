import { createTheme } from "@mui/material/styles";

const shared = {
  typography: {
    fontFamily: "'Source Sans 3', sans-serif",
    h1: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 700 },
    h2: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 700 },
    h3: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 700 },
    h4: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 600 },
  },
};

export const lightTheme = createTheme({
  ...shared,
  palette: {
    mode: "light",
    primary: { main: "#b8956a" },
    secondary: { main: "#3a3228" },
    background: { default: "#f8f4ec", paper: "#fff" },
    text: { primary: "#3a3228", secondary: "#8a7a62" },
    divider: "#e2d8c8",
  },
});

export const darkTheme = createTheme({
  ...shared,
  palette: {
    mode: "dark",
    primary: { main: "#d4a574" },
    secondary: { main: "#e8e0d4" },
    background: { default: "#1c1a16", paper: "#262220" },
    text: { primary: "#e8e0d4", secondary: "#9a8a72" },
    divider: "#3a3428",
  },
});
