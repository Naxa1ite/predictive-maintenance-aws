// DEMO MODE ONLY. Everything here is synthetic, generated in the browser, and
// is NOT produced by the trained model or AWS. The UI shows a permanent banner.
import { nextReading, scenarios } from './simulator.js'

function heuristicProbability(r) {
  // Crude stand-in for the ML model, used only in demo mode.
  const power = (r.torque * r.rotational_speed * 2 * Math.PI) / 60
  let p = 0.02 + Math.max(0, r.tool_wear - 150) / 600 + Math.max(0, r.torque - 50) / 60
  if (power < 3500 || power > 9000) p += 0.3
  return Math.min(0.99, p)
}
const riskOf = (p) => (p >= 0.5 ? 'HIGH' : p >= 0.25 ? 'MEDIUM' : 'LOW')

export function createDemoApi() {
  const preds = []
  const events = []
  let counter = 0
  const api = {
    kind: 'demo',
    async health() { return { status: 'demo', model_version: 'DEMO (no model)' } },
    async predict(reading) {
      const p = +heuristicProbability(reading).toFixed(4)
      const rec = {
        ...reading, failure_probability: p, risk_level: riskOf(p),
        predicted_class: p >= 0.5 ? 'FAILURE_PREDICTED' : 'HEALTHY_PREDICTED',
        timestamp: new Date().toISOString(), model_version: 'DEMO', source: reading.source || 'manual',
      }
      rec.prediction_id = `${rec.timestamp}#demo${counter++}`
      preds.unshift(rec)
      let ev = null
      if (rec.risk_level === 'HIGH') {
        const last = events.find((e) => e.machine_id === rec.machine_id)
        if (!last || last.maintenance_status === 'RESOLVED') {
          ev = { event_id: `${rec.timestamp}#d${counter}`, machine_id: rec.machine_id, timestamp: rec.timestamp,
            failure_probability: p, risk_level: 'HIGH', maintenance_status: 'OPEN', alert_sent: false }
          events.unshift(ev)
        }
      }
      return { ...rec, alert_triggered: false, event_id: ev && ev.event_id,
        disclaimer: 'DEMO data: heuristic in the browser, not the ML model.', input: reading }
    },
    async dashboard() {
      const latest = new Map()
      ;[...preds].reverse().forEach((p) => latest.set(p.machine_id, p))
      const machines = [...latest.values()].sort((a, b) => a.machine_id.localeCompare(b.machine_id))
      const dist = { LOW: 0, MEDIUM: 0, HIGH: 0 }
      preds.slice(0, 200).forEach((p) => { dist[p.risk_level]++ })
      const by = (r) => machines.filter((m) => m.risk_level === r).length
      return {
        summary: { total_machines: machines.length, healthy_machines: by('LOW'), medium_risk_machines: by('MEDIUM'),
          high_risk_machines: by('HIGH'), total_predictions: preds.length,
          open_events: events.filter((e) => e.maintenance_status === 'OPEN').length },
        machines, risk_distribution_recent: dist, recent_predictions: preds.slice(0, 200), recent_events: events.slice(0, 20),
      }
    },
    async predictions({ machine_id, risk_level } = {}) {
      const list = preds.filter((p) => (!machine_id || p.machine_id === machine_id) && (!risk_level || p.risk_level === risk_level))
      return { count: list.length, predictions: list.slice(0, 100) }
    },
    async events() { return { count: events.length, events } },
    async updateEvent(machine_id, event_id, status) {
      const e = events.find((x) => x.event_id === event_id)
      if (e) e.maintenance_status = status
      return { event: e }
    },
    async seed() {
      // Seed a few synthetic readings so the demo is not empty.
      for (const key of Object.keys(scenarios)) {
        for (const m of scenarios[key].machines) {
          for (let t = 0; t < 6; t++) await api.predict(nextReading(m, t))
        }
      }
    },
  }
  return api
}
