import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import Typography from "@mui/material/Typography";
import Chip from "@mui/material/Chip";
import Button from "@mui/material/Button";
import LinearProgress from "@mui/material/LinearProgress";
import Tooltip from "@mui/material/Tooltip";
import Skeleton from "@mui/material/Skeleton";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import type { Paper, PaperDetail } from "../types";
import { getItemDetail, getBibtex } from "../api";

interface DetailPanelProps {
  paper: Paper | null;
}

export default function DetailPanel({ paper }: DetailPanelProps) {
  const [detail, setDetail] = useState<PaperDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!paper) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    getItemDetail(paper.key)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [paper?.key]);

  if (!paper) return null;

  return (
    <Card
      variant="outlined"
      sx={{ p: 2.5, borderColor: "divider", bgcolor: "background.paper" }}
    >
      <Typography
        variant="caption"
        sx={{
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: 1.2,
          color: "primary.main",
          mb: 0.5,
          display: "block",
        }}
      >
        Selected Paper
      </Typography>

      <Typography
        variant="h6"
        sx={{
          fontFamily: "'Cormorant Garamond', serif",
          fontWeight: 700,
          lineHeight: 1.3,
          mb: 1,
        }}
      >
        {paper.title}
      </Typography>

      {loading ? (
        <Skeleton variant="text" width="80%" />
      ) : detail ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {detail.authors.join(", ")}
        </Typography>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {paper.creators}
        </Typography>
      )}

      <Box sx={{ display: "flex", gap: 1, mb: 1.5, flexWrap: "wrap" }}>
        <Chip label={paper.date || "n.d."} size="small" variant="outlined" />
        <Chip label={paper.itemType} size="small" variant="outlined" />
      </Box>

      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          Similarity
        </Typography>
        <LinearProgress
          variant="determinate"
          value={paper.score * 100}
          sx={{ flex: 1, height: 6, borderRadius: 3 }}
        />
        <Typography
          variant="caption"
          sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}
        >
          {paper.score.toFixed(2)}
        </Typography>
      </Box>

      {detail?.abstract && (
        <>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: 1,
              color: "text.secondary",
              display: "block",
              mb: 0.5,
            }}
          >
            Abstract
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ lineHeight: 1.6, mb: 1.5 }}
          >
            {detail.abstract.length > 300
              ? detail.abstract.slice(0, 300) + "..."
              : detail.abstract}
          </Typography>
        </>
      )}

      {detail?.tags && detail.tags.length > 0 && (
        <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", mb: 2 }}>
          {detail.tags.map((tag) => (
            <Chip key={tag} label={tag} size="small" variant="outlined" sx={{ fontSize: 11 }} />
          ))}
        </Box>
      )}

      {error && (
        <Typography variant="caption" color="error" sx={{ mb: 1, display: "block" }}>
          Zotero unavailable — showing basic info
        </Typography>
      )}

      <Box sx={{ display: "flex", gap: 1, borderTop: 1, borderColor: "divider", pt: 1.5 }}>
        {detail && (
          <Tooltip title="Open in Zotero desktop" arrow>
            <Button
              size="small"
              variant="contained"
              startIcon={<MenuBookIcon />}
              href={detail.zoteroLink}
              sx={{ textTransform: "none", fontSize: 12 }}
            >
              Zotero
            </Button>
          </Tooltip>
        )}
        <Tooltip title="Copy BibTeX to clipboard" arrow>
          <Button
            size="small"
            variant="outlined"
            startIcon={<ContentCopyIcon />}
            onClick={async () => {
              try {
                const bibtex = await getBibtex(paper.key);
                await navigator.clipboard.writeText(bibtex);
              } catch {
                await navigator.clipboard.writeText(`@article{${paper.key}}`);
              }
            }}
            sx={{ textTransform: "none", fontSize: 12 }}
          >
            BibTeX
          </Button>
        </Tooltip>
      </Box>
    </Card>
  );
}
