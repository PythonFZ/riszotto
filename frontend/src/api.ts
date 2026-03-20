import type {
  Paper,
  PaperDetail,
  GraphData,
  IndexStatus,
  SearchMode,
  Library,
} from "./types";

const BASE = "/api";

export async function searchPapers(
  query: string,
  limit = 10,
  mode: SearchMode = "semantic",
  library = "user_0"
): Promise<Paper[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    mode,
    library,
  });
  const res = await fetch(`${BASE}/search?${params}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function autocompletePapers(
  query: string,
  limit = 5,
  library = "user_0"
): Promise<Paper[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    library,
  });
  const res = await fetch(`${BASE}/autocomplete?${params}`);
  if (!res.ok) throw new Error(`Autocomplete failed: ${res.status}`);
  return res.json();
}

export async function getNeighbors(
  itemKey: string,
  cutoff = 0.35,
  depth = 2,
  library = "user_0"
): Promise<GraphData> {
  const res = await fetch(
    `${BASE}/neighbors/${itemKey}?cutoff=${cutoff}&depth=${depth}&library=${library}`
  );
  if (!res.ok) throw new Error(`Neighbors failed: ${res.status}`);
  return res.json();
}

export async function getLibraries(): Promise<Library[]> {
  const res = await fetch(`${BASE}/libraries`);
  if (!res.ok) throw new Error(`Libraries failed: ${res.status}`);
  return res.json();
}

export async function getItemDetail(
  itemKey: string
): Promise<PaperDetail> {
  const res = await fetch(`${BASE}/item/${itemKey}`);
  if (!res.ok) throw new Error(`Item detail failed: ${res.status}`);
  return res.json();
}

export async function getStatus(): Promise<IndexStatus> {
  const res = await fetch(`${BASE}/status`);
  if (!res.ok) throw new Error(`Status failed: ${res.status}`);
  return res.json();
}

export async function getBibtex(itemKey: string): Promise<string> {
  const res = await fetch(`${BASE}/item/${itemKey}/bibtex`);
  if (!res.ok) throw new Error(`BibTeX failed: ${res.status}`);
  const data = await res.json();
  return data.bibtex;
}
