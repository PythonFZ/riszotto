export interface Paper {
  key: string;
  title: string;
  creators: string;
  date: string;
  score: number;
  itemType: string;
}

export interface PaperDetail {
  key: string;
  title: string;
  authors: string[];
  abstract: string;
  tags: string[];
  date: string;
  itemType: string;
  zoteroLink: string;
}

export interface GraphNode {
  key: string;
  title: string;
  creators: string;
  date: string;
  itemType: string;
  depth: number;
  score: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  similarity: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface LibraryStatus {
  name: string;
  count: number;
}

export interface IndexStatus {
  total_papers: number;
  libraries: LibraryStatus[];
}

export type SearchMode = "semantic" | "fulltext" | "title";

export interface Library {
  name: string;
  id: string;
  type: "user" | "group";
  source: "local" | "remote";
  collection_name: string;
}
