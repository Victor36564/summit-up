import type { CatalogSave, Details, Metrics, RecommendationOptions, RecommendationRequest, RecommendationResponse, SavedTrail, Trail, Video } from "./types";

const sessionKey = "summit-up-session";
const sessionId = localStorage.getItem(sessionKey) ?? crypto.randomUUID();
localStorage.setItem(sessionKey, sessionId);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Session-ID": sessionId, ...init?.headers },
  });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Request failed");
  return response.json() as Promise<T>;
}

export const api = {
  shorts: (query: string) => request<{ items: Video[] }>(`/api/feed/shorts?query=${encodeURIComponent(query)}&limit=20`),
  search: (query: string) => request<{ items: Trail[] }>(`/api/trails/search?query=${encodeURIComponent(query)}`),
  details: (placeId: string) => request<Details>(`/api/trails/details/${encodeURIComponent(placeId)}`),
  metrics: (name: string) => request<Metrics>(`/api/trails/metrics?name=${encodeURIComponent(name)}`),
  saved: () => request<SavedTrail[]>("/api/saved"),
  toggleSaved: (trail: SavedTrail, saved: boolean) => request<{ saved: boolean; trail: SavedTrail }>("/api/saved", { method: "POST", body: JSON.stringify({ ...trail, saved }) }),
  recommendationOptions: () => request<RecommendationOptions>("/api/recommendations/options"),
  recommendations: (payload: RecommendationRequest) => request<RecommendationResponse>("/api/recommendations", { method: "POST", body: JSON.stringify(payload) }),
  toggleCatalogSaved: (trail: CatalogSave, saved: boolean) => request<{ saved: boolean; trail: SavedTrail }>("/api/saved", { method: "POST", body: JSON.stringify({ ...trail, saved }) }),
};
