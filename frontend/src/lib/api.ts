/**
 * Frontend API client communicating with FastAPI backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface Company {
  id: number;
  name: string;
  domain: string;
  created_at: string;
  updated_at: string;
}

export interface MonitoredPage {
  id: number;
  company_id: number;
  url: string;
  page_type: string;
  crawl_interval_hours: number;
  is_active: boolean;
  last_crawled_at: string | null;
  next_crawl_at: string | null;
  created_at: string;
}

export interface SnapshotItem {
  id: number;
  page_id: number;
  crawl_run_id: number;
  content_hash: string;
  title: string | null;
  captured_at: string;
  content_text: string | null;
}

export interface ChangeEventItem {
  id: number;
  page_id: number;
  previous_snapshot_id: number;
  current_snapshot_id: number;
  change_summary: string;
  is_meaningful: boolean | null;
  detected_at: string;
  diff_text: string | null;
}

export interface PageHistoryResponse {
  page_id: number;
  snapshots: SnapshotItem[];
  changes: ChangeEventItem[];
}

export interface BusinessSignal {
  id: number;
  company_id: number;
  page_id: number;
  change_event_id: number;
  signal_type: string;
  observed_change: string;
  potential_implication: string;
  evidence: string[];
  confidence: number | null;
  classification_status: string;
  model_name: string | null;
  prompt_version: string | null;
  created_at: string;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch (_) {}
    throw new Error(errorDetail);
  }

  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

export const api = {
  // Companies
  getCompanies: (skip = 0, limit = 50) =>
    request<Company[]>(`/api/v1/companies?skip=${skip}&limit=${limit}`),

  getCompany: (id: number) =>
    request<Company>(`/api/v1/companies/${id}`),

  createCompany: (name: string, domain: string) =>
    request<Company>("/api/v1/companies", {
      method: "POST",
      body: JSON.stringify({ name, domain }),
    }),

  deleteCompany: (id: number) =>
    request<void>(`/api/v1/companies/${id}`, {
      method: "DELETE",
    }),

  // Pages
  getCompanyPages: (companyId: number) =>
    request<MonitoredPage[]>(`/api/v1/companies/${companyId}/pages`),

  addPage: (companyId: number, url: string, pageType = "other", crawlInterval = 24) =>
    request<MonitoredPage>(`/api/v1/companies/${companyId}/pages`, {
      method: "POST",
      body: JSON.stringify({
        url,
        page_type: pageType,
        crawl_interval_hours: crawlInterval,
      }),
    }),

  updatePage: (pageId: number, data: Partial<MonitoredPage>) =>
    request<MonitoredPage>(`/api/v1/pages/${pageId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  triggerManualCrawl: (pageId: number) =>
    request<{ crawl_run_id: number; page_id: number; status: string; message: string }>(
      `/api/v1/pages/${pageId}/crawl`,
      { method: "POST" }
    ),

  getPageHistory: (pageId: number) =>
    request<PageHistoryResponse>(`/api/v1/pages/${pageId}/history`),

  // Signals
  getCompanySignals: (companyId: number) =>
    request<BusinessSignal[]>(`/api/v1/companies/${companyId}/signals`),

  // Health
  getHealth: () =>
    request<{ status: string; database: string }>("/api/v1/health"),
};
