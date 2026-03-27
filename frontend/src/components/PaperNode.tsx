import { memo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";

type PaperNodeData = {
  title: string;
  creators: string;
  date: string;
  score: number;
  depth: number;
  onNodeClick: (key: string) => void;
  [key: string]: unknown;
};

type PaperNodeType = Node<PaperNodeData, "paper">;

function PaperNode({ id, data }: NodeProps<PaperNodeType>) {
  const { title, creators, date, score, depth, onNodeClick } = data;
  const isCenter = depth === 0;
  const isFar = depth >= 2;

  return (
    <Tooltip
      title={
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{title}</Typography>
          <Typography variant="caption" sx={{ opacity: 0.7 }}>{creators} &middot; {date}</Typography>
          <Typography variant="caption" sx={{ display: "block", color: "primary.main", fontFamily: "'JetBrains Mono', monospace", mt: 0.5 }}>
            Similarity: {score.toFixed(2)}
          </Typography>
          {!isCenter && (
            <Typography variant="caption" sx={{ display: "block", opacity: 0.5, fontStyle: "italic", mt: 0.5 }}>
              Click to re-center
            </Typography>
          )}
        </Box>
      }
      arrow
      placement="top"
    >
      <Box
        onClick={() => !isCenter && onNodeClick(id)}
        sx={{
          px: 1.5,
          py: 1,
          borderRadius: 2,
          cursor: isCenter ? "default" : "pointer",
          maxWidth: 180,
          bgcolor: isCenter ? "secondary.main" : "background.paper",
          color: isCenter ? "background.default" : "text.primary",
          border: 2,
          borderColor: isCenter ? "primary.main" : "divider",
          opacity: isFar ? 0.7 : 1,
          fontSize: isFar ? 11 : isCenter ? 13 : 12,
          fontWeight: isCenter ? 600 : 500,
          boxShadow: 1,
          transition: "transform 0.2s, box-shadow 0.2s",
          "&:hover": isCenter
            ? {}
            : { transform: "scale(1.05)", boxShadow: 3 },
        }}
      >
        <Typography
          variant="body2"
          noWrap
          sx={{ fontSize: "inherit", fontWeight: "inherit" }}
        >
          {title}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: isCenter ? "divider" : "primary.main",
            display: "block",
          }}
        >
          {isCenter ? "center" : score.toFixed(2)}
        </Typography>
        <Handle type="source" position={Position.Right} style={{ visibility: "hidden" }} />
        <Handle type="target" position={Position.Left} style={{ visibility: "hidden" }} />
      </Box>
    </Tooltip>
  );
}

export default memo(PaperNode);
