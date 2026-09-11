import { CheckCircle2, Zap, ShieldCheck, ShieldAlert, Link2, ChevronDown, ChevronUp, AlertTriangle, User } from 'lucide-react'
import { useState } from 'react'

export default function ActionPanel({ result, isApproved, onApprove, onUndo }) {
  const [showDossier, setShowDossier] = useState(false)
  const [showChain, setShowChain] = useState(false)
  const [chainData, setChainData] = useState(null)
  const [chainLoading, setChainLoading] = useState(false)

  const getBadgeStyle = (action) => {
    switch (action) {
      case 'refund':
      case 'replace':
      case 'reissue_invoice':
        return { bg: 'var(--accent-resolved)', text: '#fff' }
      case 'request_info':
        return { bg: '#3b82f6', text: '#fff' }
      case 'answer_query':
        return { bg: '#8b5cf6', text: '#fff' }
      case 'escalate':
        return { bg: 'var(--accent-escalated)', text: '#fff' }
      default:
        return { bg: 'var(--muted)', text: '#fff' }
    }
  }

  const badgeStyle = getBadgeStyle(result.action)
  const isEscalated = result.action === 'escalate'
  const isAuditFlagged = result.audit_status === 'VETO' || (result.audit_score != null && result.audit_score > 40)

  async function loadChain() {
    if (chainData) { setShowChain(v => !v); return }
    setChainLoading(true)
    setShowChain(true)
    try {
      const res = await fetch(`/api/v1/emails/cases/${result.email_id}/verify-chain`)
      const data = await res.json()
      setChainData(data)
    } catch {
      setChainData({ error: 'Could not load chain' })
    } finally {
      setChainLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '0 24px 24px 24px', flex: 1, overflowY: 'auto' }}>
        <div className="receipt-container animate-print" style={{ margin: '24px 0' }}>
          <div className="receipt-top" />
          <div className="receipt-content">
            <div className="receipt-header" style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Action Receipt</h3>
              <div className="receipt-date text-muted">{new Date().toLocaleString()}</div>
            </div>

            {/* Main Summary Card */}
            <div className="summary-card" style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: '16px', padding: '20px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="summary-label" style={{ fontSize: '0.85rem' }}>Reference ID</span>
                <span className="summary-value font-mono" style={{ textAlign: 'left' }}>{result.reference_id || 'N/A'}</span>
              </div>
              {result.order && (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="summary-label" style={{ fontSize: '0.85rem' }}>Order ID</span>
                    <span className="summary-value font-mono" style={{ textAlign: 'left' }}>{result.order.id}</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="summary-label" style={{ fontSize: '0.85rem' }}>Item</span>
                    <span className="summary-value" style={{ textAlign: 'left' }}>{result.order.item}</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="summary-label" style={{ fontSize: '0.85rem' }}>Amount</span>
                    <span className="summary-value font-mono" style={{ textAlign: 'left' }}>${result.order.amount.toFixed(2)}</span>
                  </div>
                </>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '8px', borderTop: '1px dashed var(--border-strong)' }}>
                <span className="summary-label" style={{ fontSize: '0.85rem' }}>Status</span>
                <div style={{ padding: '4px 0' }}>
                  <span style={{
                    display: 'inline-block', padding: '6px 16px', borderRadius: '16px',
                    fontSize: '13px', fontWeight: 600, textTransform: 'uppercase',
                    backgroundColor: badgeStyle.bg, color: badgeStyle.text,
                  }}>
                    {result.action === 'escalate' ? 'Escalated to Team' :
                     result.action === 'request_info' ? 'Awaiting Customer' :
                     result.action === 'answer_query' ? 'Auto-Resolved' :
                     result.action === 'refund' ? 'Refund Processed' :
                     result.action === 'replace' ? 'Replacement Arranged' : 'Invoice Reissued'}
                  </span>
                </div>
              </div>
            </div>

            {/* ── Auditor Critic Badge ─────────────────────────────── */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '12px 16px', borderRadius: '10px', marginBottom: '12px',
              background: isAuditFlagged ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
              border: `1px solid ${isAuditFlagged ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`,
            }}>
              {isAuditFlagged
                ? <ShieldAlert size={18} color="#ef4444" />
                : <ShieldCheck size={18} color="#22c55e" />}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: isAuditFlagged ? '#ef4444' : '#22c55e' }}>
                  {isAuditFlagged ? 'AUDITOR VETO' : 'AUDITOR APPROVED'}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                  Risk Score: {result.audit_score ?? 'N/A'}/100
                </div>
              </div>
              <span style={{
                fontSize: '0.75rem', fontWeight: 600, padding: '3px 10px',
                borderRadius: '999px', background: isAuditFlagged ? '#ef4444' : '#22c55e', color: '#fff',
              }}>
                {result.audit_status || 'PASS'}
              </span>
            </div>

            {/* ── Evidence Chain Button ───────────────────────────── */}
            <button
              id="btn-verify-chain"
              onClick={loadChain}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 14px', borderRadius: '10px', marginBottom: '12px',
                background: 'var(--surface)', border: '1px solid var(--border)',
                cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600, color: 'var(--ink)',
                justifyContent: 'space-between', transition: 'background 0.15s',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                <Link2 size={15} color="var(--muted)" /> SHA-256 Evidence Chain
              </span>
              {showChain ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {showChain && (
              <div style={{
                padding: '12px', borderRadius: '10px', marginBottom: '12px',
                background: 'var(--bg-paper)', border: '1px solid var(--border)',
                fontFamily: 'monospace', fontSize: '0.72rem', color: 'var(--ink)'
              }}>
                {chainLoading ? (
                  <span style={{ color: 'var(--muted)' }}>Verifying chain…</span>
                ) : chainData?.error ? (
                  <span style={{ color: '#ef4444' }}>{chainData.error}</span>
                ) : (
                  <>
                    <div style={{ color: chainData?.is_valid ? 'var(--accent-resolved)' : '#ef4444', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {chainData?.is_valid ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                      {chainData?.is_valid ? 'CHAIN INTACT' : 'TAMPERED DETECTED'} · {chainData?.chain_length ?? 0} events
                    </div>
                    {chainData?.head_hash && (
                      <div style={{ color: 'var(--muted)', marginBottom: '8px' }}>HEAD: {chainData.head_hash.substring(0, 32)}…</div>
                    )}
                    {chainData?.entries?.map((e, i) => (
                      <div key={i} style={{ marginTop: '4px', borderBottom: i < chainData.entries.length - 1 ? '1px dashed var(--border-strong)' : 'none', paddingBottom: '4px' }}>
                        <span style={{ color: 'var(--muted)', fontWeight: 600 }}>#{e.sequence}</span> {e.event_type}
                        <div style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>{e.hash}</div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}

            {/* ── Escalation Dossier ─────────────────────────────── */}
            {isEscalated && result.escalation_dossier && (
              <>
                <button
                  id="btn-show-dossier"
                  onClick={() => setShowDossier(v => !v)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                    padding: '10px 14px', borderRadius: '10px', marginBottom: '12px',
                    background: 'var(--bg-paper)', border: '1px solid var(--border)',
                    cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600, color: 'var(--ink)',
                    justifyContent: 'space-between',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                    <AlertTriangle size={15} color="var(--accent-escalated)" /> Escalation Dossier
                  </span>
                  {showDossier ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
                {showDossier && (
                  <div style={{
                    padding: '16px', borderRadius: '10px', marginBottom: '16px',
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '12px',
                  }}>
                    <div>
                      <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 700 }}>Customer</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
                        <User size={13} color="var(--muted)" />
                        <span style={{ fontWeight: 600 }}>{result.escalation_dossier.customer_name}</span>
                        <span style={{ color: 'var(--muted)' }}>·</span>
                        <span style={{ color: 'var(--muted)' }}>{result.escalation_dossier.customer_email}</span>
                      </div>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 700 }}>Sentiment</span>
                      <div style={{ marginTop: '4px', color: 'var(--accent-escalated)', fontWeight: 600 }}>{result.escalation_dossier.sentiment}</div>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 700 }}>Escalation Reason</span>
                      <div style={{ marginTop: '4px', color: 'var(--ink)' }}>{result.escalation_dossier.primary_reason}</div>
                    </div>
                    {result.escalation_dossier.auditor_flags?.length > 0 && (
                      <div>
                        <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 700 }}>Auditor Flags</span>
                        <ul style={{ marginTop: '6px', paddingLeft: '16px', color: '#ef4444' }}>
                          {result.escalation_dossier.auditor_flags.map((f, i) => <li key={i}>{f}</li>)}
                        </ul>
                      </div>
                    )}
                    <div style={{
                      padding: '10px 14px', borderRadius: '8px',
                      background: 'var(--bg-paper)', border: '1px dashed var(--border-strong)',
                    }}>
                      <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 700 }}>Recommended Action</span>
                      <div style={{ marginTop: '4px', fontWeight: 600, color: 'var(--ink)' }}>{result.escalation_dossier.recommended_action_description}</div>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Email Reply Preview */}
            <div className="receipt-step">
              <div className="step-title" style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                Drafted reply
              </div>
              <iframe
                srcDoc={result.drafted_reply_html || `<p style="font-family:sans-serif;color:#888;padding:16px">No HTML preview available.</p>`}
                style={{ width: '100%', height: '380px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: '#fff' }}
                sandbox="allow-same-origin"
                title="Email preview"
              />
            </div>
          </div>
        </div>
      </div>

      {result.action === 'escalate' && !isApproved ? (
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', gap: '12px', flexShrink: 0 }}>
          <button id="btn-approve-send" className="btn-primary" style={{ flex: 1, margin: 0, justifyContent: 'center' }} onClick={onApprove}>
            Mark as Resolved
          </button>
          <button id="btn-undo" className="btn-undo" style={{ margin: 0, flexShrink: 0 }} onClick={onUndo}>
            Undo
          </button>
        </div>
      ) : (
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', background: 'var(--surface)', textAlign: 'center', color: 'var(--muted)', fontSize: '0.85rem' }}>
          <span style={{ color: 'var(--accent-resolved)', fontWeight: 600 }}>✓</span> {isApproved ? 'Resolved by Team / Admin' : 'Reply has been sent to customer automatically.'}
        </div>
      )}
    </div>
  )
}
