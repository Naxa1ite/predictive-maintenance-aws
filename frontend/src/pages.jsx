import React, { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, Disclaimer, Empty, RiskBadge, SourceTag, Stat } from './components.jsx'
import { RISK_COLORS, STATUS_LABELS, fmtTime, pct } from './risk.js'

export function Overview({ data }) {
  const s = data.summary
  return (
    <>
      <div className="stats">
        <Stat label="Monitored machines" value={s.total_machines} />
        <Stat label="Healthy (low risk)" value={s.healthy_machines} tone="low" />
        <Stat label="Medium risk" value={s.medium_risk_machines} tone="medium" />
        <Stat label="High risk" value={s.high_risk_machines} tone="high" />
        <Stat label="Total predictions" value={s.total_predictions} />
      </div>
      <Card title="Recent high-risk events">
        {data.recent_events.length === 0 ? <Empty title="No high-risk events">None recorded yet.</Empty> : (
          <ul className="list">
            {data.recent_events.slice(0, 5).map((e) => (
              <li key={e.event_id}><RiskBadge level={e.risk_level} /> <b>{e.machine_id}</b> · {pct(e.failure_probability)} · {fmtTime(e.timestamp)} · {STATUS_LABELS[e.maintenance_status] || e.maintenance_status}</li>
            ))}
          </ul>
        )}
      </Card>
      <Disclaimer />
    </>
  )
}

export function Machines({ data }) {
  if (!data.machines.length) return <Empty title="No machines yet">Submit a prediction or start the simulator to see machines here.</Empty>
  return (
    <Card title="Machine monitoring (latest reading per machine)">
      <div className="table-wrap">
        <table>
          <thead><tr><th>Machine</th><th>Risk</th><th>Failure prob.</th><th>Air K</th><th>Process K</th><th>RPM</th><th>Torque Nm</th><th>Wear min</th><th>Updated</th></tr></thead>
          <tbody>
            {data.machines.map((m) => (
              <tr key={m.machine_id}>
                <td><b>{m.machine_id}</b> <SourceTag source={m.source} /></td>
                <td><RiskBadge level={m.risk_level} /></td>
                <td>{pct(m.failure_probability)}</td>
                <td>{m.air_temperature}</td><td>{m.process_temperature}</td><td>{m.rotational_speed}</td><td>{m.torque}</td><td>{m.tool_wear}</td>
                <td>{fmtTime(m.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Disclaimer />
    </Card>
  )
}

const BLANK = { machine_id: 'MACHINE-001', air_temperature: 298.1, process_temperature: 308.6, rotational_speed: 1550, torque: 42, tool_wear: 120, machine_type: 'M' }
const FIELDS = [
  ['air_temperature', 'Air temperature (K)'], ['process_temperature', 'Process temperature (K)'],
  ['rotational_speed', 'Rotational speed (rpm)'], ['torque', 'Torque (Nm)'], ['tool_wear', 'Tool wear (min)'],
]

export function PredictForm({ api, onDone }) {
  const [form, setForm] = useState(BLANK)
  const [state, setState] = useState({ status: 'idle' })
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  async function submit(e) {
    e.preventDefault()
    setState({ status: 'loading' })
    const body = { ...form, source: 'manual' }
    FIELDS.forEach(([k]) => { body[k] = Number(form[k]) })
    try {
      const result = await api.predict(body)
      setState({ status: 'ok', result })
      if (onDone) onDone()
    } catch (err) {
      setState({ status: 'error', message: err.message, details: err.details })
    }
  }
  const r = state.result
  return (
    <div className="two-col">
      <Card title="Submit sensor reading">
        <form onSubmit={submit} className="form">
          <label>Machine ID<input value={form.machine_id} onChange={set('machine_id')} required maxLength={40} /></label>
          {FIELDS.map(([k, label]) => (
            <label key={k}>{label}<input type="number" step="any" value={form[k]} onChange={set(k)} required /></label>
          ))}
          <label>Machine type
            <select value={form.machine_type} onChange={set('machine_type')}>
              <option value="L">L (low quality)</option><option value="M">M (medium)</option><option value="H">H (high)</option>
            </select>
          </label>
          <button type="submit" disabled={state.status === 'loading'}>{state.status === 'loading' ? 'Predicting…' : 'Predict failure risk'}</button>
        </form>
      </Card>
      <Card title="Result">
        {state.status === 'idle' && <Empty title="No prediction yet">Fill in the form and submit.</Empty>}
        {state.status === 'loading' && <p>Calling the prediction API…</p>}
        {state.status === 'error' && (
          <div className="error" role="alert"><b>Error:</b> {state.message}
            {state.details && state.details.length > 0 && <ul>{state.details.map((d) => <li key={d}>{d}</li>)}</ul>}
          </div>
        )}
        {state.status === 'ok' && (
          <div className="result">
            <div className="result-head"><RiskBadge level={r.risk_level} /><span className="big">{pct(r.failure_probability)}</span></div>
            <p><b>Predicted class:</b> {r.predicted_class === 'FAILURE_PREDICTED' ? 'Failure predicted' : 'Healthy predicted'}</p>
            <p><b>Machine:</b> {r.machine_id} · <b>Model:</b> {r.model_version} · <b>Time:</b> {fmtTime(r.timestamp)}</p>
            <p><b>Input:</b> {Object.entries(r.input).map(([k, v]) => `${k}=${v}`).join(', ')}</p>
            {r.alert_triggered && <p className="alert-note">An email alert was sent for this machine.</p>}
            <p className="disclaimer">This is a model estimate, not a confirmed physical machine condition.</p>
          </div>
        )}
      </Card>
    </div>
  )
}

export function History({ api, refreshKey }) {
  const [filters, setFilters] = useState({ machine_id: '', risk_level: '' })
  const [state, setState] = useState({ status: 'loading', rows: [] })
  React.useEffect(() => {
    let live = true
    setState((s) => ({ ...s, status: 'loading' }))
    api.predictions(filters).then((r) => live && setState({ status: 'ok', rows: r.predictions }))
      .catch((e) => live && setState({ status: 'error', rows: [], message: e.message }))
    return () => { live = false }
  }, [api, filters, refreshKey])
  return (
    <Card title="Historical predictions">
      <div className="filters">
        <label>Machine ID<input value={filters.machine_id} onChange={(e) => setFilters({ ...filters, machine_id: e.target.value.trim() })} placeholder="e.g. MACHINE-001" /></label>
        <label>Risk level
          <select value={filters.risk_level} onChange={(e) => setFilters({ ...filters, risk_level: e.target.value })}>
            <option value="">All</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option>
          </select>
        </label>
      </div>
      {state.status === 'loading' && <p>Loading…</p>}
      {state.status === 'error' && <div className="error" role="alert">{state.message}</div>}
      {state.status === 'ok' && state.rows.length === 0 && <Empty title="No predictions found">Submit a reading or start the simulator, or clear the filters.</Empty>}
      {state.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Time</th><th>Machine</th><th>Result</th><th>Risk</th><th>Probability</th><th>Torque</th><th>RPM</th><th>Wear</th><th>Source</th></tr></thead>
            <tbody>
              {state.rows.map((p) => (
                <tr key={p.prediction_id}>
                  <td>{fmtTime(p.timestamp)}</td><td>{p.machine_id}</td>
                  <td>{p.predicted_class === 'FAILURE_PREDICTED' ? 'Failure predicted' : 'Healthy predicted'}</td>
                  <td><RiskBadge level={p.risk_level} /></td><td>{pct(p.failure_probability)}</td>
                  <td>{p.torque}</td><td>{p.rotational_speed}</td><td>{p.tool_wear}</td><td><SourceTag source={p.source} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Disclaimer />
    </Card>
  )
}

export function Charts({ data }) {
  const machines = data.machines.map((m) => m.machine_id)
  const [sel, setSel] = useState('')
  const counts = {}
  data.recent_predictions.forEach((p) => { counts[p.machine_id] = (counts[p.machine_id] || 0) + 1 })
  const busiest = [...machines].sort((a, b) => (counts[b] || 0) - (counts[a] || 0))[0] || ''
  const machine = sel || busiest
  const series = useMemo(
    () => [...data.recent_predictions].reverse().filter((p) => !machine || p.machine_id === machine)
      .map((p) => ({ t: new Date(p.timestamp).toLocaleTimeString(), prob: Number(p.failure_probability), torque: Number(p.torque), rpm: Number(p.rotational_speed), wear: Number(p.tool_wear) })),
    [data, machine])
  const dist = Object.entries(data.risk_distribution_recent).map(([name, value]) => ({ name, value }))
  const health = [
    { name: 'Healthy', value: data.summary.healthy_machines, k: 'LOW' },
    { name: 'Medium', value: data.summary.medium_risk_machines, k: 'MEDIUM' },
    { name: 'High', value: data.summary.high_risk_machines, k: 'HIGH' },
  ]
  if (!data.recent_predictions.length) return <Empty title="No data to chart">Charts appear once predictions exist.</Empty>
  return (
    <>
      <div className="two-col">
        <Card title="Failure-risk distribution (recent predictions)">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart><Pie data={dist} dataKey="value" nameKey="name" outerRadius={85} label>
              {dist.map((d) => <Cell key={d.name} fill={RISK_COLORS[d.name]} />)}</Pie><Tooltip /><Legend /></PieChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Machine health summary (latest state)">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={health}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip />
              <Bar dataKey="value">{health.map((h) => <Cell key={h.name} fill={RISK_COLORS[h.k]} />)}</Bar></BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <Card title="Prediction history over time" actions={
        <select aria-label="Machine" value={machine} onChange={(e) => setSel(e.target.value)}>{machines.map((m) => <option key={m}>{m}</option>)}</select>}>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" /><YAxis domain={[0, 1]} /><Tooltip />
            <Line type="monotone" dataKey="prob" name="Failure probability" stroke="#d63a3a" dot={false} /></LineChart>
        </ResponsiveContainer>
      </Card>
      <Card title={`Sensor trends — ${machine}`}>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" /><YAxis yAxisId="a" /><YAxis yAxisId="b" orientation="right" /><Tooltip /><Legend />
            <Line yAxisId="a" type="monotone" dataKey="torque" name="Torque (Nm)" stroke="#2b6cb0" dot={false} />
            <Line yAxisId="a" type="monotone" dataKey="wear" name="Tool wear (min)" stroke="#6b46c1" dot={false} />
            <Line yAxisId="b" type="monotone" dataKey="rpm" name="Speed (rpm)" stroke="#2f9e44" dot={false} /></LineChart>
        </ResponsiveContainer>
      </Card>
    </>
  )
}

export function Alerts({ api, data, onChange }) {
  const [err, setErr] = useState('')
  async function setStatus(e, status) {
    try { setErr(''); await api.updateEvent(e.machine_id, e.event_id, status); onChange() } catch (x) { setErr(x.message) }
  }
  if (!data.recent_events.length) return <Empty title="No high-risk events">High-risk predictions create an event and an email alert.</Empty>
  return (
    <Card title="High-risk events and maintenance status">
      {err && <div className="error" role="alert">{err}</div>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Machine</th><th>Probability</th><th>Email sent</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>
            {data.recent_events.map((e) => (
              <tr key={e.event_id}>
                <td>{fmtTime(e.timestamp)}</td><td>{e.machine_id}</td><td>{pct(e.failure_probability)}</td>
                <td>{e.alert_sent ? 'Yes' : 'No'}</td><td>{STATUS_LABELS[e.maintenance_status] || e.maintenance_status}</td>
                <td className="actions">
                  <button className="small" onClick={() => setStatus(e, 'ACKNOWLEDGED')} disabled={e.maintenance_status !== 'OPEN'}>Acknowledge</button>
                  <button className="small" onClick={() => setStatus(e, 'UNDER_MAINTENANCE')} disabled={e.maintenance_status === 'UNDER_MAINTENANCE' || e.maintenance_status === 'RESOLVED'}>Under maintenance</button>
                  <button className="small" onClick={() => setStatus(e, 'RESOLVED')} disabled={e.maintenance_status === 'RESOLVED'}>Resolve</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Disclaimer />
    </Card>
  )
}
