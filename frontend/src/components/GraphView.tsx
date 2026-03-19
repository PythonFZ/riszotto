import { useEffect, useCallback } from "react";
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  type Node,
  type Edge,
} from "@xyflow/react";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import "@xyflow/react/dist/style.css";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import CircularProgress from "@mui/material/CircularProgress";
import PaperNode from "./PaperNode";
import GraphControls from "./GraphControls";
import type { GraphData } from "../types";

const nodeTypes = { paper: PaperNode };

interface GraphViewProps {
  graphData: GraphData | null;
  cutoff: number;
  depth: number;
  onCutoffChange: (v: number) => void;
  onDepthChange: (v: number) => void;
  onNodeClick: (key: string) => void;
  loading: boolean;
}

interface SimNode extends SimulationNodeDatum {
  id: string;
}

interface SimLink extends SimulationLinkDatum<SimNode> {
  similarity: number;
}

function computeLayout(
  graphData: GraphData,
  onNodeClick: (key: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const simNodes: SimNode[] = graphData.nodes.map((n) => ({
    id: n.key,
    x: Math.random() * 500,
    y: Math.random() * 500,
  }));

  const simLinks: SimLink[] = graphData.edges.map((e) => ({
    source: e.source,
    target: e.target,
    similarity: e.similarity,
  }));

  const simulation = forceSimulation<SimNode>(simNodes)
    .force(
      "link",
      forceLink<SimNode, SimLink>(simLinks)
        .id((d) => d.id)
        .distance((d) => {
          // High similarity => shorter distance
          const sim = d.similarity;
          return 50 + (1 - sim) * 300;
        }),
    )
    .force("charge", forceManyBody().strength(-200))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide(60))
    .stop();

  // Run simulation synchronously
  for (let i = 0; i < 150; i++) {
    simulation.tick();
  }

  const nodeMap = new Map(graphData.nodes.map((n) => [n.key, n]));

  const nodes: Node[] = simNodes.map((sn) => {
    const gn = nodeMap.get(sn.id)!;
    return {
      id: sn.id,
      type: "paper",
      position: { x: sn.x ?? 0, y: sn.y ?? 0 },
      data: {
        title: gn.title,
        creators: gn.creators,
        date: gn.date,
        score: gn.score,
        depth: gn.depth,
        onNodeClick,
      },
    };
  });

  const edges: Edge[] = graphData.edges.map((e, i) => ({
    id: `e-${e.source}-${e.target}-${i}`,
    source: e.source,
    target: e.target,
    style: {
      strokeWidth: 1 + e.similarity * 2,
      opacity: 0.3 + e.similarity * 0.5,
      stroke: "#888",
    },
    animated: false,
  }));

  return { nodes, edges };
}

function GraphViewInner({
  graphData,
  cutoff,
  depth,
  onCutoffChange,
  onDepthChange,
  onNodeClick,
  loading,
}: GraphViewProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const stableOnNodeClick = useCallback(
    (key: string) => onNodeClick(key),
    [onNodeClick],
  );

  useEffect(() => {
    if (!graphData || graphData.nodes.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }
    const layout = computeLayout(graphData, stableOnNodeClick);
    setNodes(layout.nodes);
    setEdges(layout.edges);
  }, [graphData, stableOnNodeClick, setNodes, setEdges]);

  // Empty / loading states
  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: 2,
          color: "text.secondary",
        }}
      >
        <CircularProgress size={32} />
        <Typography variant="body2">Loading...</Typography>
      </Box>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: 1,
          color: "text.secondary",
        }}
      >
        <Typography variant="h6" sx={{ opacity: 0.5, fontWeight: 500 }}>
          Search to explore
        </Typography>
        <Typography variant="body2" sx={{ opacity: 0.4 }}>
          Enter a paper title to build a citation graph
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ position: "relative", width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} />
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          style={{ borderRadius: 8 }}
        />
      </ReactFlow>
      <GraphControls
        cutoff={cutoff}
        depth={depth}
        onCutoffChange={onCutoffChange}
        onDepthChange={onDepthChange}
      />
    </Box>
  );
}

export default function GraphView(props: GraphViewProps) {
  return (
    <ReactFlowProvider>
      <GraphViewInner {...props} />
    </ReactFlowProvider>
  );
}
