import React from 'react'
import { RISK_LABELS } from './risk.js'

const ICON = { LOW: '●', MEDIUM: '▲', HIGH: '■' }

export function RiskBadge({ level }) {
  return <span className={`badge badge-${level}`}>{ICON[level]} {RISK_LABELS[level] || level}</span>
}

export function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ''}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export function Empty({ title, children }) {
  return <div className="empty"><strong>{title}</strong><p>{children}</p></div>
}

export function Card({ title, children, actions }) {
  return (
    <section className="card">
      <header className="card-head"><h2>{title}</h2>{actions}</header>
      {children}
    </section>
  )
}

export function Disclaimer() {
  return <p className="disclaimer">Values shown are <b>model predictions</b>, not confirmed physical machine conditions. Academic prototype — not for safety-critical use.</p>
}

export function SourceTag({ source }) {
  return source === 'simulated'
    ? <span className="tag tag-sim" title="Synthetic reading, not a real IoT measurement">SIMULATED</span>
    : <span className="tag">manual</span>
}
