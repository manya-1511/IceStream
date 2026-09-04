/**
 * Minimal API service abstraction.
 *
 * The base URL is always read from VITE_API_URL — never hardcode
 * http://localhost:8000 inside components. This gets expanded with
 * real endpoints (orders, incidents, lineage, etc.) in later days.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL as string;

export interface HealthResponse {
  status: string;
  services: {
    api: string;
    postgres: string;
    redis: string;
  };
  details?: Record<string, string>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getHealth: () => request<HealthResponse>("/health"),
  getRoot: () => request<{ service: string; status: string }>("/"),
};
