import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { createApi, loadConfig } from './api.js'
import { createDemoApi } from './demo.js'
import { Empty } from './components.jsx'
import { Alerts, Charts, History, Machines, Overview, PredictForm } from './pages.jsx'
import { SimulatorPanel } from './SimulatorPanel.jsx'

const TABS = ['Overview', 'Machines', 'Predict', 'History', 'Charts', 'Alerts', 'Simulator']

export default function App() {
  const [cfg, setCfg] = useState(null)
  const [demo, setDemo] = useState(false)
  const [tab, setTab] = useState('Overview')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => { loadConfig().then(setCfg) }, [])
  const api = useMemo(() => {
    if (demo) return createDemoApi()
    if (cfg && cfg.apiBaseUrl) return createApi(cfg.apiBaseUrl)
    return null
  }, [cfg, demo])

  const refresh = useCallback(async () => {
    if (!api) return
    setLoading(true)
    try { setData(await api.dashboard()); setError('') } catch (e) { setError(e.message) }
    setLoading(false)
    setRefreshKey((k) => k + 1)
  }, [api])

  useEffect(() => { setData(null); if (api) refresh() }, [api, refresh])

  if (!cfg) return <div className="boot">Loading…</div>
  const unconfigured = !cfg.apiBaseUrl && !demo

  return (
    <div className="app">
      <header className="topbar">
        <div><h1>Predictive Maintenance Monitor</h1><small>AWS · Lambda · DynamoDB · SNS — academic prototype</small></div>
        <div className="top-actions">
          {api && <button className="ghost" onClick={refresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>}
          {cfg.apiBaseUrl && <button className="ghost" onClick={() => setDemo((d) => !d)}>{demo ? 'Exit demo mode' : 'Demo mode'}</button>}
        </div>
      </header>
      {demo && (
        <div className="banner banner-demo" role="status"><b>DEMO MODE</b> — synthetic data generated in your browser with a simple heuristic. <b>Nothing here comes from AWS or the trained model.</b>
          <button className="small" onClick={async () => { await api.seed(); refresh() }}>Load sample data</button></div>
      )}
      {!demo && api && <div className="banner banner-live" role="status">Connected to AWS backend: <code>{cfg.apiBaseUrl}</code></div>}
      {unconfigured && (
        <div className="banner banner-warn" role="alert">
          <b>No backend configured.</b> <code>config.json</code> has no <code>apiBaseUrl</code>, so the AWS stack is not deployed or not linked.
          <button className="small" onClick={() => setDemo(true)}>Start demo mode (synthetic data)</button>
        </div>
      )}
      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => <button key={t} className={t === tab ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>)}
      </nav>
      <main>
        {error && <div className="error" role="alert"><b>Backend error:</b> {error}</div>}
        {!api && <Empty title="Waiting for a backend">Deploy the stack or use demo mode.</Empty>}
        {api && !data && !error && <p>Loading dashboard…</p>}
        {api && data && tab === 'Overview' && <Overview data={data} />}
        {api && data && tab === 'Machines' && <Machines data={data} />}
        {api && tab === 'Predict' && <PredictForm api={api} onDone={refresh} />}
        {api && tab === 'History' && <History api={api} refreshKey={refreshKey} />}
        {api && data && tab === 'Charts' && <Charts data={data} />}
        {api && data && tab === 'Alerts' && <Alerts api={api} data={data} onChange={refresh} />}
        {api && tab === 'Simulator' && <SimulatorPanel api={api} onTick={refresh} />}
      </main>
      <footer>Predictions are model estimates for demonstration, not confirmed failures.</footer>
    </div>
  )
}
