export const RISK_COLORS = { LOW: '#2f9e44', MEDIUM: '#e08a00', HIGH: '#d63a3a' }
export const RISK_LABELS = { LOW: 'Low risk', MEDIUM: 'Medium risk', HIGH: 'High risk' }
export const pct = (p) => `${(Number(p) * 100).toFixed(1)}%`
export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—')
export const STATUS_LABELS = {
  OPEN: 'Open', ACKNOWLEDGED: 'Acknowledged', UNDER_MAINTENANCE: 'Under maintenance', RESOLVED: 'Resolved',
}
