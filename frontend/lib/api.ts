/**
 * Backend client. Same-origin: next.config.ts rewrites /api/* to FastAPI, so there
 * is no CORS preflight and no backend port in the browser.
 */

export type Company = {
  ticker: string;
  name_ar: string;
  name_en: string;
  sector_ar: string;
  sector_en: string;
  /** "exact": the company IS the query, so the price card leads.
   *  "prefix": a question about it, so the answer leads. */
  match?: "exact" | "prefix";
};

export type Citation = {
  id: number;
  title: string; title_en?: string | null;
  publisher: string;
  url: string;
  doc_type: string;
  published_at: number | null;
  source: string;
  companies: { ticker: string; name: string }[];
};

export type Passage = {
  doc_id: number;
  text: string;
  title: string;
  distance: number;
  doc_type: string;
};

export type Answer = {
  mode: "extractive";
  status: "ok" | "below_threshold" | "no_results";
  text: string | null;
  passages: Passage[];
  citations: Citation[];
  locale: "ar" | "en";
  threshold: number;
  reason?: "no_anchor" | "too_far";
  best_distance?: number;
};

export type SearchResult = {
  id: number;
  title: string; title_en?: string | null;
  publisher: string;
  url: string;
  doc_type: string;
  published_at: number | null;
  source: string;
  tickers: string[];
  distance: number;
};

export type SearchResponse = {
  query: string;
  entity: Company | null;
  answer: Answer;
  results: SearchResult[];
};

/** Every market payload carries this. `delayed` and `stale` are never inferred. */
export type Envelope<T> = {
  data: T;
  source: "live" | "cache" | "sample";
  stale: boolean;
  delayed: boolean;
  as_of: string | null;
  fetched_at: number;
};

export type NewsDoc = {
  id: number;
  title: string; title_en?: string | null;
  publisher: string;
  url: string;
  doc_type: string;
  published_at: number | null;
  source: string;
  tickers: string[];
};

export type Health = {
  status: string;
  documents: number;
  corpus_loaded: boolean;
  corpus_documents: number;
  model_loaded: boolean;
  warm_up: { state: string; seconds: number | null };
  requests_today: number;
  budget_remaining: number;
  watchlist: string[];
};

export type SeriesPoint = {
  date: string; open: number | null; high: number | null; low: number | null;
  close: number | null; volume: number; sma20: number | null; sma50: number | null; z: number | null;
};

export type Series = {
  symbol: string; name_ar: string; name_en: string; sector_ar: string; sector_en: string;
  points: SeriesPoint[]; last: number | null; period_change: number | null;
  high_52: number | null; low_52: number | null; trend: "above" | "below" | null; source: "sample";
};

export type WatchItem = {
  ticker: string; name_ar: string; name_en: string; sector_ar: string; sector_en: string;
  last: number | null; change: number | null; change_real: boolean;
  spark: (number | null)[]; quote_source: "cache" | "sample"; stale: boolean;
};

export type SectorHeat = { sector_en: string; sector_ar: string; change: number; weight: number; source: "live" | "sample" };
export type TrendItem = { ticker: string; name_ar: string; name_en: string; count: number };
export type CalendarItem = { id: number; title: string; title_en?: string | null; doc_type: string; published_at: number | null; url: string; publisher: string };
export type BriefDoc = { id: number; title: string; title_en?: string | null; doc_type: string; publisher: string; url: string; published_at: number | null; tickers: string[] };
export type Brief = { total_documents: number; by_type: Record<string, number>; tagged_documents: number; latest: BriefDoc[] };
export type Dashboard = { brief: Brief; watchlist: WatchItem[]; sectors: SectorHeat[]; trending: TrendItem[]; calendar: CalendarItem[] };
export type Performance = { "5d"?: number | null; "1m"?: number | null; "3m"?: number | null; "6m"?: number | null; period?: number | null };
export type CompanyData = { entity: Company; quote: Envelope<Record<string, unknown>> | null; series: Series | null; performance: Performance; signal: Signal; news: NewsDoc[]; context: NewsDoc[] };

export type SignalComponent = { key: string; vote: number; detail_en: string; detail_ar: string; real?: boolean };
export type Signal = {
  label: "bullish" | "neutral" | "bearish" | "unknown"; score: number; max_score: number;
  components: SignalComponent[]; rsi: number | null; advice: false; disclaimer: true;
};
export type RecentItem = { id: number; title: string; title_en?: string | null; doc_type: string; url: string; published_at: number | null; tickers: string[] };
export type ResearchGroup = { doc_type: string; docs: NewsDoc[] };
export type ResearchEntity = { ticker: string; name_ar: string; name_en: string; count: number };
export type ResearchData = { query: string; answer: Answer; result_count: number; groups: ResearchGroup[]; entities: ResearchEntity[]; timeline: NewsDoc[] };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error?.message ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export type Persona = {
  id: string;
  name_ar: string;
  name_en: string;
  role_ar: string;
  role_en: string;
};

export type DmMessage = {
  id: number;
  sender: "me" | "persona";
  body: string;
  doc_id: number | null;
  created_at: number;
  /** Resolved live from doc_id, so a shared card never drifts from the document. */
  document: {
    id: number;
    title: string; title_en?: string | null;
    url: string;
    publisher: string;
    doc_type: string;
    published_at: number | null;
  } | null;
};

export type DmThread = {
  id: number;
  persona: Persona;
  messages: DmMessage[];
};

export type DmThreadSummary = {
  id: number;
  persona: Persona;
  message_count: number;
  last: { body: string; doc_id: number | null; created_at: number; sender: string } | null;
};

export const api = {
  search: (body: { query: string; k?: number; doc_type?: string; ticker?: string }) =>
    call<SearchResponse>("/api/search", { method: "POST", body: JSON.stringify(body) }),
  news: (symbol: string) =>
    call<{ symbol: string; entity: Company | null; documents: NewsDoc[] }>(
      `/api/news/${symbol}`,
    ),
  quote: (symbol: string) => call<Envelope<Record<string, unknown>>>(`/api/quote/${symbol}`),
  health: () => call<Health>("/api/health"),
  dashboard: () => call<Dashboard>("/api/dashboard"),
  history: (symbol: string) => call<Series>(`/api/history/${symbol}`),
  company: (symbol: string) => call<CompanyData>(`/api/company/${symbol}`),
  recent: (limit = 6) => call<{ recent: RecentItem[] }>(`/api/recent?limit=${limit}`),
  research: (query: string) => call<ResearchData>("/api/research", { method: "POST", body: JSON.stringify({ query, k: 24 }) }),
  dmThreads: () => call<{ threads: DmThreadSummary[]; sample: boolean }>("/api/dm/threads"),
  dmThread: (id: number) => call<DmThread & { sample: boolean }>(`/api/dm/threads/${id}`),
  dmSend: (id: number, body: { body?: string; doc_id?: number }) =>
    call<DmThread>(`/api/dm/threads/${id}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
