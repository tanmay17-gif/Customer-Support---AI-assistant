import { useState, useEffect } from 'react'
import { CheckCircle2, Zap, AlertTriangle, Users } from 'lucide-react'

export default function BroadcastTab({ businessId, showToast }) {
  const [clusters, setClusters] = useState([])
  const [loading, setLoading] = useState(false)
  const [clustering, setClustering] = useState(false)

  const fetchClusters = async () => {
    setLoading(true)
    try {
      const res = await fetch(`/api/v1/emails/clusters/list?business_id=${businessId}`)
      if (res.ok) setClusters(await res.json())
    } catch {}
    setLoading(false)
  }

  const triggerClustering = async () => {
    setClustering(true)
    try {
      showToast('Grouping similar issues...', 'info')
      await fetch(`/api/v1/emails/clusters/trigger?business_id=${businessId}`, { method: 'POST' })
      await fetchClusters()
      showToast('Clustering complete.', 'success')
    } catch {
      showToast('Failed to cluster.', 'error')
    }
    setClustering(false)
  }

  const approveCluster = async (clusterId) => {
    try {
      await fetch(`/api/v1/emails/clusters/${clusterId}/approve`, { method: 'POST' })
      showToast('Broadcast approved and sent.', 'success')
      fetchClusters()
    } catch {
      showToast('Failed to approve broadcast.', 'error')
    }
  }

  useEffect(() => {
    fetchClusters()
  }, [businessId])

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: '40px', width: '100%' }}>
      <div style={{ maxWidth: 680, width: '100%', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div className="summary-card" style={{ margin: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={{ margin: 0 }}>Active Broadcasts</h2>
            <button className="btn-primary" onClick={triggerClustering} disabled={clustering}>
              {clustering ? 'Analyzing...' : 'Find Similar Issues'}
            </button>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: 16 }}>
            The AI automatically groups similar customer issues together. Approve a broadcast to resolve all affected tickets at once.
          </p>

          {loading ? (
             <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)' }}>Loading...</div>
          ) : clusters.length === 0 ? (
            <div style={{
              textAlign: 'center', padding: '32px', borderRadius: '12px',
              background: 'var(--bg)', border: '1px dashed var(--border)',
            }}>
              <CheckCircle2 size={32} style={{ margin: '0 auto 8px', display: 'block' }} color="var(--accent-resolved)" />
              <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>No pending broadcasts.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {clusters.map(c => (
                <div key={c.id} style={{
                  padding: '16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--surface)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                    <div>
                      <strong style={{ fontSize: '0.95rem' }}>{c.root_cause_summary}</strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', color: 'var(--accent-escalated)', fontSize: '0.8rem', fontWeight: 600 }}>
                        <Users size={14} /> {c.email_ids.length} customers affected
                      </div>
                    </div>
                  </div>
                  <div style={{
                    padding: '12px', borderRadius: '8px', background: 'var(--bg-paper)',
                    border: '1px dashed var(--border-strong)', fontSize: '0.85rem', marginBottom: '16px'
                  }} dangerouslySetInnerHTML={{ __html: c.broadcast_draft_html }} />
                  <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => approveCluster(c.id)}>
                    Approve &amp; Resolve All ({c.email_ids.length})
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
