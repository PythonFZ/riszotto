import type { Paper, PaperDetail, GraphData, IndexStatus } from "./types";

const BASE = "/api";

export async function searchPapers(
  query: string,
  limit = 10
): Promise<Paper[]> {
  const res = await fetch(
    `${BASE}/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function autocompletePapers(
  query: string,
  limit = 5
): Promise<Paper[]> {
  const res = await fetch(
    `${BASE}/autocomplete?q=${encodeURIComponent(query)}&limit=${limit}`
  );
  if (!res.ok) throw new Error(`Autocomplete failed: ${res.status}`);
  return res.json();
}

export async function getNeighbors(
  itemKey: string,
  cutoff = 0.35,
  depth = 2
): Promise<GraphData> {
  const res = await fetch(
    `${BASE}/neighbors/${itemKey}?cutoff=${cutoff}&depth=${depth}`
  );
  if (!res.ok) throw new Error(`Neighbors failed: ${res.status}`);
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
