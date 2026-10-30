import React, { useEffect, useRef, useState } from 'react'
import { Card } from './components.jsx'
import { nextReading, scenarioMachines, scenarios } from './simulator.js'

const MAX_TICKS = 40

// Runs ONLY after the user presses Start; stops on Stop, on unmount, or after MAX_TICKS rounds.
export function SimulatorPanel({ api, onTick }) {
  const [selected, setSelected] = useState(['normal'])
  const [running, setRunning] = useState(false)
  const [log, setLog] = useState([])
  const [intervalSec, setIntervalSec] = useState(3)
  const tickRef = useRef(0)

  useEffect(() => {
    if (!running) return undefined
    const id = setInterval(async () => {
      const t = tickRef.current++
      if (t >= MAX_TICKS) { setRunning(false); return }
      for (const m of scenarioMachines(selected)) {
        try {
          const res = await api.predict(nextReading(m, t))
          setLog((l) => [`${new Date().toLocaleTimeString()} ${res.machine_id}: ${res.risk_level} ${(res.failure_probability * 100).toFixed(1)}%${res.alert_triggered ? ' (alert sent)' : ''}`, ...l].slice(0, 12))
        } catch (e) {
          setLog((l) => [`${new Date().toLocaleTimeString()} ${m.machine_id}: ERROR ${e.message}`, ...l].slice(0, 12))
        }
      }
      if (onTick) onTick()
    }, intervalSec * 1000)
    return () => clearInterval(id)
  }, [running, selected, api, intervalSec, onTick])

  const toggle = (k) => setSelected((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]))
  return (
    <Card title="Sensor simulator (synthetic data)">
      <p className="disclaimer">Generates <b>simulated</b> readings — not real IoT measurements — and sends them to the {api.kind === 'demo' ? 'DEMO (in-browser)' : 'real AWS'} prediction API. The model decides the risk level; scenarios only describe plausible sensor ranges. Stops automatically after {MAX_TICKS} rounds.</p>
      <div className="scenarios">
        {Object.entries(scenarios).map(([k, s]) => (
          <label key={k} className="check"><input type="checkbox" checked={selected.includes(k)} disabled={running} onChange={() => toggle(k)} />
            <span><b>{s.label}</b><br /><small>{s.description}</small></span></label>
        ))}
      </div>
      <label>Interval (seconds)<input type="number" min="1" max="60" value={intervalSec} disabled={running} onChange={(e) => setIntervalSec(Math.max(1, Number(e.target.value) || 3))} /></label>
      <div className="row">
        {!running
          ? <button disabled={!selected.length} onClick={() => { tickRef.current = 0; setRunning(true) }}>Start simulator</button>
          : <button className="danger" onClick={() => setRunning(false)}>Stop simulator</button>}
        <span className={running ? 'pulse on' : 'pulse'}>{running ? 'Running' : 'Stopped'}</span>
      </div>
      <pre className="log" aria-live="polite">{log.length ? log.join('\n') : 'No simulated readings sent yet.'}</pre>
    </Card>
  )
}
