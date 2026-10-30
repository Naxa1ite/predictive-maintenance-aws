// Thin client for the real backend (API Gateway + Lambda). No mock data here.
export class ApiError extends Error {
  constructor(message, status, details) {
    super(message)
    this.status = status
    this.details = details || []
  }
}

export async function loadConfig(fetchFn = fetch) {
  try {
    const r = await fetchFn('/config.json', { cache: 'no-store' })
    if (!r.ok) return { apiBaseUrl: '' }
    const cfg = await r.json()
    return { apiBaseUrl: (cfg.apiBaseUrl || '').replace(/\/$/, '') }
  } catch {
    return { apiBaseUrl: '' }
  }
}

export function createApi(baseUrl, fetchFn = (...a) => fetch(...a)) {
  async function call(method, path, body) {
    let res
    try {
      res = await fetchFn(baseUrl + path, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      })
    } catch {
      throw new ApiError('Cannot reach the API. Check your connection and the API URL.', 0)
    }
    let data = null
    try { data = await res.json() } catch { /* empty body */ }
    if (!res.ok) throw new ApiError((data && data.error) || `Request failed (${res.status})`, res.status, data && data.details)
    return data
  }
  const qs = (o) => {
    const p = new URLSearchParams(Object.entries(o).filter(([, v]) => v !== '' && v != null))
    const s = p.toString()
    return s ? `?${s}` : ''
  }
  return {
    kind: 'aws',
    health: () => call('GET', '/health'),
    predict: (reading) => call('POST', '/predict', reading),
    dashboard: () => call('GET', '/dashboard'),
    predictions: (filters = {}) => call('GET', `/predictions${qs(filters)}`),
    events: () => call('GET', '/events'),
    updateEvent: (machine_id, event_id, maintenance_status) =>
      call('PATCH', '/events', { machine_id, event_id, maintenance_status }),
  }
}
