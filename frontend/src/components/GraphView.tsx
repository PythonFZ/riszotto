import { useEffect, useCallback, useState } from "react";
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
import ELK, { type ElkNode, type ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";
import "@xyflow/react/dist/style.css";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import CircularProgress from "@mui/material/CircularProgress";
import PaperNode from "./PaperNode";
import GraphControls from "./GraphControls";
import type { GraphData } from "../types";

const nodeTypes = { paper: PaperNode };
const elk = new ELK();

const NODE_WIDTH = 170;
const NODE_HEIGHT = 50;

interface GraphViewProps {
  graphData: GraphData | null;
  cutoff: number;
  depth: number;
  onCutoffChange: (v: number) => void;
  onDepthChange: (v: number) => void;
  onNodeClick: (key: string) => void;
  loading: boolean;
}

async function computeLayout(
  graphData: GraphData,
  onNodeClick: (key: string) => void,
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  const elkGraph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.spacing.nodeNode": "80",
      "elk.layered.spacing.nodeNodeBetweenLayers": "120",
      "elk.layered.spacing.edgeNodeBetweenLayers": "40",
      "elk.edgeRouting": "SPLINES",
    },
    children: graphData.nodes.map((n) => ({
      id: n.key,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    })) as ElkNode[],
    edges: graphData.edges.map((e, i) => ({
      id: `e-${e.source}-${e.target}-${i}`,
      sources: [e.source],
      targets: [e.target],
    })) as ElkExtendedEdge[],
  };

  const layout = await elk.layout(elkGraph);
  const nodeMap = new Map(graphData.nodes.map((n) => [n.key, n]));

  const nodes: Node[] = (layout.children ?? []).map((elkNode) => {
    const gn = nodeMap.get(elkNode.id)!;
    return {
      id: elkNode.id,
      type: "paper",
      position: { x: elkNode.x ?? 0, y: elkNode.y ?? 0 },
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
  const [layoutLoading, setLayoutLoading] = useState(false);

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
    let cancelled = false;
    setLayoutLoading(true);
    computeLayout(graphData, stableOnNodeClick).then((layout) => {
      if (!cancelled) {
        setNodes(layout.nodes);
        setEdges(layout.edges);
        setLayoutLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [graphData, stableOnNodeClick, setNodes, setEdges]);

  if (loading || layoutLoading) {
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
          Enter a paper title to build a similarity graph
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
