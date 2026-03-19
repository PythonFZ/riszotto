import { useState, useEffect, useCallback, useMemo } from "react";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import { lightTheme, darkTheme } from "./theme";
import TopBar from "./components/TopBar";
import SearchBar from "./components/SearchBar";
import DetailPanel from "./components/DetailPanel";
import GraphView from "./components/GraphView";
import { getStatus, getNeighbors } from "./api";
import type { Paper, GraphData, IndexStatus } from "./types";

export default function App() {
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem("riszotto-dark-mode") === "true";
  });
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [cutoff, setCutoff] = useState(0.35);
  const [depth, setDepth] = useState(2);

  const theme = useMemo(() => (darkMode ? darkTheme : lightTheme), [darkMode]);

  const toggleDarkMode = useCallback(() => {
    setDarkMode((prev) => {
      const next = !prev;
      localStorage.setItem("riszotto-dark-mode", String(next));
      return next;
    });
  }, []);

  // Fetch status on mount
  useEffect(() => {
    getStatus().then(setStatus).catch(() => {});
  }, []);

  // Fetch graph when paper, cutoff, or depth changes
  const fetchGraph = useCallback(
    async (paperKey: string) => {
      setGraphLoading(true);
      try {
        const data = await getNeighbors(paperKey, cutoff, depth);
        setGraphData(data);
      } catch {
        setGraphData(null);
      } finally {
        setGraphLoading(false);
      }
    },
    [cutoff, depth]
  );

  useEffect(() => {
    if (selectedPaper) {
      fetchGraph(selectedPaper.key);
    }
  }, [selectedPaper?.key, cutoff, depth, fetchGraph]);

  const handlePaperSelect = useCallback((paper: Paper) => {
    setSelectedPaper(paper);
  }, []);

  const handleNodeClick = useCallback(
    (key: string) => {
      // Re-center: find the node in current graph data to build a Paper object
      const node = graphData?.nodes.find((n) => n.key === key);
      if (node) {
        setSelectedPaper({
          key: node.key,
          title: node.title,
          creators: node.creators,
          date: node.date,
          score: node.score,
          itemType: node.itemType,
        });
      }
    },
    [graphData]
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        <TopBar
          status={status}
          darkMode={darkMode}
          onToggleDarkMode={toggleDarkMode}
        />
        <Box sx={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Left Panel */}
          <Box
            sx={{
              width: 300,
              minWidth: 300,
              borderRight: 1,
              borderColor: "divider",
              display: "flex",
              flexDirection: "column",
              bgcolor: "background.default",
            }}
          >
            <Box sx={{ p: 2, pb: 0 }}>
              <SearchBar onSelect={handlePaperSelect} />
            </Box>
            <Box sx={{ flex: 1, overflow: "auto", p: 2 }}>
              <DetailPanel paper={selectedPaper} />
            </Box>
          </Box>

          {/* Right Panel — Graph */}
          <Box sx={{ flex: 1, position: "relative" }}>
            <GraphView
              graphData={graphData}
              cutoff={cutoff}
              depth={depth}
              onCutoffChange={setCutoff}
              onDepthChange={setDepth}
              onNodeClick={handleNodeClick}
              loading={graphLoading}
            />
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
