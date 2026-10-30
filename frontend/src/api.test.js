import { describe, expect, it, vi } from 'vitest'
import { ApiError, createApi, loadConfig } from './api.js'
import { createDemoApi } from './demo.js'
import { nextReading, scenarios } from './simulator.js'

const ok = (body) => ({ ok: true, status: 200, json: async () => body })

describe('api client', () => {
  it('POSTs predictions as JSON to /predict', async () => {
    const f = vi.fn().mockResolvedValue(ok({ risk_level: 'LOW' }))
    const api = createApi('https://x.test', f)
    await api.predict({ machine_id: 'A' })
    expect(f.mock.calls[0][0]).toBe('https://x.test/predict')
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ machine_id: 'A' })
  })

  it('builds filter query strings and skips empty ones', async () => {
    const f = vi.fn().mockResolvedValue(ok({ predictions: [] }))
    await createApi('https://x.test', f).predictions({ machine_id: 'A', risk_level: '' })
    expect(f.mock.calls[0][0]).toBe('https://x.test/predictions?machine_id=A')
  })

  it('surfaces validation errors with details', async () => {
    const f = vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ error: 'Validation failed', details: ['torque is required'] }) })
    await expect(createApi('https://x.test', f).predict({})).rejects.toMatchObject({ status: 422, details: ['torque is required'] })
  })

  it('reports network failure clearly', async () => {
    const f = vi.fn().mockRejectedValue(new TypeError('fail'))
    await expect(createApi('https://x.test', f).dashboard()).rejects.toBeInstanceOf(ApiError)
  })

  it('PATCHes event status', async () => {
    const f = vi.fn().mockResolvedValue(ok({ event: {} }))
    await createApi('https://x.test', f).updateEvent('M', 'e1', 'ACKNOWLEDGED')
    expect(f.mock.calls[0][1].method).toBe('PATCH')
    expect(JSON.parse(f.mock.calls[0][1].body).maintenance_status).toBe('ACKNOWLEDGED')
  })

  it('loadConfig returns empty URL when config is missing', async () => {
    expect(await loadConfig(async () => ({ ok: false }))).toEqual({ apiBaseUrl: '' })
    expect(await loadConfig(async () => ok({ apiBaseUrl: 'https://a.b/' }))).toEqual({ apiBaseUrl: 'https://a.b' })
  })
})

describe('simulator + demo', () => {
  it('generates readings tagged simulated within valid ranges', () => {
    const r = nextReading(scenarios.normal.machines[0], 3)
    expect(r.source).toBe('simulated')
    expect(r.process_temperature).toBeGreaterThan(r.air_temperature)
    expect(r.torque).toBeGreaterThanOrEqual(0)
  })

  it('demo api is labelled as demo, never as aws', async () => {
    const api = createDemoApi()
    expect(api.kind).toBe('demo')
    const res = await api.predict(nextReading(scenarios.high.machines[0], 0))
    expect(res.model_version).toBe('DEMO')
    expect((await api.dashboard()).summary.total_predictions).toBe(1)
  })
})
