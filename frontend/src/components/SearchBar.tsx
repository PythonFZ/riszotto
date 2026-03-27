import { useState, useCallback, useRef } from "react";
import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import ToggleButton from "@mui/material/ToggleButton";
import SearchIcon from "@mui/icons-material/Search";
import InputAdornment from "@mui/material/InputAdornment";
import type { Paper, SearchMode } from "../types";
import { autocompletePapers, searchPapers } from "../api";

interface SearchBarProps {
  onSelect: (paper: Paper) => void;
  library: string;
}

export default function SearchBar({ onSelect, library }: SearchBarProps) {
  const [options, setOptions] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("semantic");

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleInputChange = useCallback(
    (_: unknown, value: string) => {
      setInputValue(value);
      if (debounceTimer.current) clearTimeout(debounceTimer.current);

      if (value.length < 2) {
        setOptions([]);
        return;
      }

      debounceTimer.current = setTimeout(async () => {
        setLoading(true);
        try {
          const results =
            searchMode === "semantic"
              ? await autocompletePapers(value, 5, library)
              : await searchPapers(value, 10, searchMode, library);
          setOptions(results);
        } catch {
          setOptions([]);
        } finally {
          setLoading(false);
        }
      }, 300);
    },
    [searchMode, library]
  );

  return (
    <Box>
      <Autocomplete
        freeSolo
        options={options}
        loading={loading}
        inputValue={inputValue}
        onInputChange={handleInputChange}
        getOptionLabel={(option) =>
          typeof option === "string" ? option : option.title
        }
        onChange={(_, value) => {
          if (value && typeof value !== "string") {
            onSelect(value);
          }
        }}
        renderOption={({ key, ...props }, option) => (
          <Box
            component="li"
            key={key}
            {...props}
            sx={{
              display: "flex",
              justifyContent: "space-between",
              gap: 1,
            }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
                {option.title}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                {option.creators} &middot; {option.date}
              </Typography>
            </Box>
            {option.score > 0 && (
              <Typography
                variant="caption"
                sx={{
                  fontFamily: "'JetBrains Mono', monospace",
                  color: "primary.main",
                  flexShrink: 0,
                }}
              >
                {option.score.toFixed(2)}
              </Typography>
            )}
          </Box>
        )}
        renderInput={(params) => (
          <TextField
            {...params}
            placeholder={
              searchMode === "semantic"
                ? "Search papers semantically..."
                : searchMode === "fulltext"
                  ? "Search all fields..."
                  : "Search title / author / year..."
            }
            size="small"
            slotProps={{
              input: {
                ...params.InputProps,
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon
                      sx={{ color: "primary.main", fontSize: 20 }}
                    />
                  </InputAdornment>
                ),
              },
            }}
          />
        )}
        sx={{ width: "100%" }}
      />
      <ToggleButtonGroup
        value={searchMode}
        exclusive
        onChange={(_, v) => v && setSearchMode(v)}
        size="small"
        sx={{ mt: 1, "& .MuiToggleButton-root": { fontSize: 11, py: 0.25, textTransform: "none" } }}
      >
        <ToggleButton value="semantic">Semantic</ToggleButton>
        <ToggleButton value="title">Title</ToggleButton>
        <ToggleButton value="fulltext">Full text</ToggleButton>
      </ToggleButtonGroup>
    </Box>
  );
}
