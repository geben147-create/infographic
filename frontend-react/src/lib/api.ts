const API_BASE = import.meta.env.VITE_API_BASE || ''

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${body}`)
  }
  return res.json()
}

// --- Types ---

export interface RunSummary {
  workflow_id: string
  channel_id: string
  status: string
  total_cost_usd: number | null
  youtube_url?: string | null
  video_path?: string | null
  thumbnail_path?: string | null
  started_at: string | null
  completed_at: string | null
  error_message?: string | null
}

export interface DashboardRunsResponse {
  runs: RunSummary[]
  total: number
  limit: number
  offset: number
}

export interface ChannelCostSummary {
  channel_id: string
  total_cost_usd: number
  run_count: number
}

export interface DashboardCostsResponse {
  total_cost_usd: number
  days: number
  by_channel: ChannelCostSummary[]
}

export interface DailyCostEntry {
  date: string
  cost: number
  run_count: number
}

export interface DailyCostsResponse {
  days: number
  data: DailyCostEntry[]
}

export interface ServiceCost {
  service: string
  total_cost_usd: number
}

export interface CostsByServiceResponse {
  days: number
  services: ServiceCost[]
  grand_total_usd: number
}

export interface HealthResponse {
  status: string
  temporal: boolean
  sqlite: boolean
  disk_free_gb: number
}

export interface PipelineStatusResponse {
  workflow_id: string
  status: string
  current_step?: string | null
  scenes_total?: number | null
  scenes_done?: number | null
  cost_so_far_usd?: number | null
  youtube_url?: string | null
  error?: string | null
  started_at?: string | null
  completed_at?: string | null
}

export interface CostLineItem {
  service: string
  step: string
  amount_usd: number
  resolution?: string | null
}

export interface CostDetailResponse {
  workflow_id: string
  channel_id: string
  total_cost_usd: number
  breakdown: CostLineItem[]
}

export interface TriggerResponse {
  workflow_id: string
  status: string
  channel_id: string
  topic: string
  estimated_cost_usd?: number | null
}

export interface ChannelWithStats {
  channel_id: string
  niche: string
  language: string
  video_model: string
  image_model: string
  tts_model: string
  llm_model: string
  tags: string[]
  vgen_enabled: boolean
  quality_gate_enabled: boolean
  total_runs: number
  success_count: number
  failed_count: number
  success_rate: number
  avg_cost_usd: number
}

export interface ChannelListResponse {
  channels: ChannelWithStats[]
  total: number
}

export interface WorkerInfo {
  name: string
  task_queue: string
  max_concurrent: number
  description: string
}

export interface SystemInfoService {
  name: string
  version: string | null
  status: string
  url?: string | null
}

export interface AlertEntry {
  ts: string
  level: string
  message: string
  details: string
}

// --- API Functions ---

export const api = {
  // Dashboard
  getRuns: (params?: { limit?: number; offset?: number; channel_id?: string }) => {
    const qs = new URLSearchParams()
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.offset) qs.set('offset', String(params.offset))
    if (params?.channel_id) qs.set('channel_id', params.channel_id)
    return fetchJson<DashboardRunsResponse>(`/api/dashboard/runs?${qs}`)
  },

  getCosts: (params?: { days?: number; channel_id?: string }) => {
    const qs = new URLSearchParams()
    if (params?.days) qs.set('days', String(params.days))
    if (params?.channel_id) qs.set('channel_id', params.channel_id)
    return fetchJson<DashboardCostsResponse>(`/api/dashboard/costs?${qs}`)
  },

  getDailyCosts: (days = 30, channel_id?: string) => {
    const qs = new URLSearchParams({ days: String(days) })
    if (channel_id) qs.set('channel_id', channel_id)
    return fetchJson<DailyCostsResponse>(`/api/dashboard/costs/daily?${qs}`)
  },

  getCostsByService: (days = 30) =>
    fetchJson<CostsByServiceResponse>(`/api/dashboard/costs/by-service?days=${days}`),

  // Health
  getHealth: () => fetchJson<HealthResponse>('/health'),

  // Pipeline
  triggerPipeline: (topic: string, channel_id: string) =>
    fetchJson<TriggerResponse>('/api/pipeline/trigger', {
      method: 'POST',
      body: JSON.stringify({ topic, channel_id }),
    }),

  getPipelineStatus: (id: string) =>
    fetchJson<PipelineStatusResponse>(`/api/pipeline/status/${id}`),

  getPipelineCost: (id: string) =>
    fetchJson<CostDetailResponse>(`/api/pipeline/cost/${id}`),

  approvePipeline: (id: string, approved: boolean, reason = '') =>
    fetchJson<{ signalled: boolean }>(`/api/pipeline/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved, reason }),
    }),

  cancelPipeline: (id: string) =>
    fetchJson<{ cancelled: boolean }>(`/api/pipeline/${id}`, { method: 'DELETE' }),

  // Channels
  getChannels: () => fetchJson<ChannelListResponse>('/api/channels'),
  getChannel: (id: string) => fetchJson<ChannelWithStats>(`/api/channels/${id}`),

  // System
  getWorkers: () =>
    fetchJson<{ workers: WorkerInfo[] }>('/api/system/workers'),

  getSystemInfo: () =>
    fetchJson<{ services: SystemInfoService[] }>('/api/system/info'),

  getAlerts: (limit = 20) =>
    fetchJson<{ alerts: AlertEntry[]; total: number }>(`/api/system/alerts?limit=${limit}`),

  // Sync
  triggerSync: () =>
    fetchJson<{ workflow_id: string; status: string }>('/api/sync/sheets', { method: 'POST' }),
}
