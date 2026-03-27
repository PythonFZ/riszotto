import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import Box from "@mui/material/Box";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import type { IndexStatus, Library } from "../types";

interface TopBarProps {
  status: IndexStatus | null;
  libraries: Library[];
  selectedLibrary: string;
  onLibraryChange: (collectionName: string) => void;
  darkMode: boolean;
  onToggleDarkMode: () => void;
}

export default function TopBar({
  status,
  libraries,
  selectedLibrary,
  onLibraryChange,
  darkMode,
  onToggleDarkMode,
}: TopBarProps) {
  return (
    <AppBar
      position="static"
      elevation={0}
      sx={{
        bgcolor: "background.paper",
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <Toolbar variant="dense" sx={{ gap: 2 }}>
        <Typography
          variant="h6"
          sx={{
            fontFamily: "'Cormorant Garamond', serif",
            fontWeight: 700,
            color: "text.primary",
          }}
        >
          riszotto
          <Box component="span" sx={{ color: "primary.main", fontWeight: 400, ml: 0.5 }}>
            search
          </Box>
        </Typography>

        {status && (
          <Box sx={{ display: "flex", gap: 2, ml: 2 }}>
            <Typography variant="caption" color="text.secondary">
              <Box component="span" sx={{ fontFamily: "'JetBrains Mono', monospace", color: "text.primary" }}>
                {status.total_papers.toLocaleString()}
              </Box>{" "}
              papers
            </Typography>
            <Typography variant="caption" color="text.secondary">
              <Box component="span" sx={{ fontFamily: "'JetBrains Mono', monospace", color: "text.primary" }}>
                {status.libraries.length}
              </Box>{" "}
              {status.libraries.length === 1 ? "library" : "libraries"}
            </Typography>
          </Box>
        )}

        {libraries.length > 1 && (
          <Select
            value={selectedLibrary}
            onChange={(e) => onLibraryChange(e.target.value)}
            size="small"
            sx={{
              fontSize: 12,
              ml: 1,
              "& .MuiSelect-select": { py: 0.5 },
            }}
          >
            {libraries.map((lib) => (
              <MenuItem key={lib.collection_name} value={lib.collection_name} sx={{ fontSize: 12 }}>
                {lib.name}
              </MenuItem>
            ))}
          </Select>
        )}

        <Box sx={{ flexGrow: 1 }} />

        <IconButton onClick={onToggleDarkMode} size="small" color="inherit" sx={{ color: "text.secondary" }}>
          {darkMode ? <Brightness7Icon fontSize="small" /> : <Brightness4Icon fontSize="small" />}
        </IconButton>
      </Toolbar>
    </AppBar>
  );
}
