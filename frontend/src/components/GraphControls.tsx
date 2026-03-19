import Box from "@mui/material/Box";
import Slider from "@mui/material/Slider";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";

interface GraphControlsProps {
  cutoff: number;
  depth: number;
  onCutoffChange: (value: number) => void;
  onDepthChange: (value: number) => void;
}

export default function GraphControls({
  cutoff,
  depth,
  onCutoffChange,
  onDepthChange,
}: GraphControlsProps) {
  return (
    <Paper
      elevation={0}
      sx={(theme) => ({
        position: "absolute",
        top: 16,
        right: 16,
        zIndex: 10,
        p: 2,
        width: 200,
        bgcolor: theme.palette.mode === "dark"
          ? "rgba(38,34,32,0.92)"
          : "rgba(255,255,255,0.92)",
        backdropFilter: "blur(8px)",
        border: 1,
        borderColor: "divider",
        borderRadius: 2,
      })}
    >
      <Box sx={{ mb: 1.5 }}>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "text.secondary",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          Similarity cutoff
          <Box
            component="span"
            sx={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {cutoff.toFixed(2)}
          </Box>
        </Typography>
        <Slider
          value={cutoff}
          onChange={(_, v) => onCutoffChange(v as number)}
          min={0}
          max={1}
          step={0.05}
          size="small"
        />
      </Box>
      <Box>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "text.secondary",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          Depth
          <Box
            component="span"
            sx={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {depth}
          </Box>
        </Typography>
        <Slider
          value={depth}
          onChange={(_, v) => onDepthChange(v as number)}
          min={1}
          max={4}
          step={1}
          marks
          size="small"
        />
      </Box>
    </Paper>
  );
}
