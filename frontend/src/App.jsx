import { useState, useEffect, useCallback } from 'react'
import './index.css'
import Navbar from './components/Navbar'
import EmailList from './components/EmailList'
import EmailDetail from './components/EmailDetail'
import ActionPanel from './components/ActionPanel'
import BroadcastTab from './components/BroadcastTab'
import { CheckCircle2, AlertCircle, Info, Mail, Sparkles, Inbox, ShieldCheck, AlertTriangle, RefreshCw } from 'lucide-react'

const API = '/api/v1'

export default function App() {
  const [emails, setEmails]             = useState([])
  const [selectedId, setSelectedId]     = useState(null)
  const [results, setResults]           = useState({})
  const [loading, setLoading]           = useState(false)
  const [loadingEmails, setLoadingEmails] = useState(true)
  const [gmailConnected, setGmailConnected] = useState(false)
  const [gmailEmail, setGmailEmail]     = useState(null)
  const [toast, setToast]               = useState(null)
  const [activeTab, setActiveTab]       = useState('inbox')
  const [brandConfig, setBrandConfig]   = useState({ brand_name: 'SupportAI', brand_logo_url: '' })
  const [selectedBusiness, setSelectedBusiness] = useState('biz_tech')
  const [proposals, setProposals]       = useState([])
  const [proposalsLoading, setProposalsLoading] = useState(false)

  useEffect(() => {
    fetchDemoEmails()
    checkGmailStatus()
    fetchConfig()

    // Auto-refresh every 20 seconds silently so dashboard reflects background actions without flickering
    const refreshInterval = setInterval(() => {
      fetchDemoEmails(true)
      checkGmailStatus()
    }, 20000)
    return () => clearInterval(refreshInterval)
  }, [])

  useEffect(() => {
    if (activeTab === 'settings') fetchProposals()
  }, [activeTab, selectedBusiness])

  async function fetchConfig() {
    try {
      const res = await fetch(`${API}/config`)
      if (res.ok) setBrandConfig(await res.json())
    } catch {}
  }

  async function fetchDemoEmails(silent = false) {
    if (!silent) setLoadingEmails(true)
    try {
      const res = await fetch(`${API}/emails/`)
      if (!res.ok) throw new Error('Backend not reachable')
      setEmails(await res.json())
    } catch (err) {
      console.warn('Backend not running, using empty list:', err.message)
      if (!silent) setEmails([])
    } finally {
      if (!silent) setLoadingEmails(false)
    }
  }

  async function checkGmailStatus() {
    try {
      const res = await fetch(`${API}/gmail/status`)
      const data = await res.json()
      setGmailConnected(data.authenticated)
      setGmailEmail(data.email)
    } catch {}
  }

  async function triggerPoll() {
    try {
      showToast('Checking Gmail for new emails...', 'info')
      await fetch(`${API}/gmail/poll`, { method: 'POST' })
      fetchDemoEmails()
    } catch {}
  }

  async function fetchProposals() {
    setProposalsLoading(true)
    try {
      const res = await fetch(`${API}/emails/policy-proposals/list?business_id=${selectedBusiness}`)
      if (res.ok) setProposals(await res.json())
    } catch {}
    setProposalsLoading(false)
  }

  async function handleProposal(id, action) {
    try {
      await fetch(`${API}/emails/policy-proposals/${id}/${action}`, { method: 'POST' })
      showToast(action === 'approve' ? 'Policy amendment approved & RAG re-indexed!' : 'Proposal rejected.', action === 'approve' ? 'success' : 'info')
      fetchProposals()
    } catch {
      showToast('Action failed', 'error')
    }
  }

  // Sort newest first
  const sortedEmails = [...emails].sort((a, b) => new Date(b.received_at) - new Date(a.received_at))
  let displayEmails = sortedEmails
  if (activeTab === 'inbox')     displayEmails = sortedEmails.filter(e => !e.outcome)
  else if (activeTab === 'resolved')  displayEmails = sortedEmails.filter(e => e.outcome === 'resolved')
  else if (activeTab === 'escalated') displayEmails = sortedEmails.filter(e => e.outcome === 'escalated')

  const selectedEmail  = displayEmails.find(e => e.id === selectedId) || null
  const selectedResult = results[selectedId] || null

  useEffect(() => {
    if (selectedEmail && selectedEmail.processed && !selectedResult) {
      // Fetch result from backend
      fetch(`${API}/emails/${selectedId}/result`)
        .then(res => res.json())
        .then(data => {
          setResults(prev => ({ ...prev, [selectedId]: data }))
        })
        .catch(err => console.error("Failed to load result:", err))
    }
  }, [selectedId, selectedEmail, selectedResult])

  async function processEmail(email) {
    setLoading(true)
    showToast('Analysing email...', 'info')
    try {
      const payload = { ...email, business_id: selectedBusiness }
      const res = await fetch(`${API}/emails/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Processing failed')
      }
      const data = await res.json()
      setResults(prev => ({ ...prev, [email.id]: data }))
      setEmails(prev => prev.map(e => e.id === email.id
        ? { ...e, action: data.action, processed: true, outcome: null } : e
      ))
      showToast('Analysis complete!', 'success')
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error')
      console.error('Processing failed:', err)
    } finally {
      setLoading(false)
    }
  }

  async function approveAndSend(emailId) {
    try {
      const res  = await fetch(`${API}/emails/${emailId}/approve`, { method: 'POST' })
      const data = await res.json()
      setEmails(prev => prev.map(e => {
        if (e.id !== emailId) return e
        return { ...e, outcome: e.action === 'escalate' ? 'escalated' : 'resolved', approved: true }
      }))
      showToast(data.sent ? 'Reply approved and sent via Gmail!' : 'Reply approved and logged.', 'success')
    } catch {
      showToast('Approval failed', 'error')
    }
  }

  async function undoAction(emailId) {
    try {
      await fetch(`${API}/emails/${emailId}/undo`, { method: 'POST' })
      setResults(prev => { const r = { ...prev }; delete r[emailId]; return r })
      setEmails(prev => prev.map(e => e.id === emailId
        ? { ...e, action: null, processed: false, outcome: null, approved: false } : e
      ))
      showToast('Action reversed — order restored.', 'info')
    } catch {
      showToast('Undo failed', 'error')
    }
  }

  function showToast(msg, type = 'info') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  const processedCount = Object.keys(results).length

  return (
    <>
      <Navbar
        brandConfig={brandConfig}
        totalEmails={emails.length}
        processedCount={processedCount}
        gmailConnected={gmailConnected}
        gmailEmail={gmailEmail}
        activeTab={activeTab}
        onTabChange={tab => { setActiveTab(tab); setSelectedId(null) }}
        selectedBusiness={selectedBusiness}
        onBusinessChange={biz => { setSelectedBusiness(biz); setSelectedId(null); setResults({}) }}
      />

      {/* Toast */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'success' && <CheckCircle2 size={18} color="var(--accent-resolved)" />}
          {toast.type === 'error'   && <AlertCircle  size={18} color="var(--accent-escalated)" />}
          {toast.type === 'info'    && <Info          size={18} color="var(--muted)" />}
          <span>{toast.msg}</span>
        </div>
      )}

      {activeTab === 'settings' ? (
        <div className="dashboard" style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: '40px' }}>
          <div style={{ maxWidth: 680, width: '100%', display: 'flex', flexDirection: 'column', gap: '24px' }}>

            {/* Gmail Status */}
            <div className="summary-card" style={{ margin: 0 }}>
              <h2 style={{ marginBottom: 16 }}>Settings</h2>
              <div className="summary-row">
                <span className="summary-label">Gmail Integration</span>
                <span className="summary-value" style={{ color: gmailConnected ? 'var(--accent-resolved)' : 'var(--muted)' }}>
                  {gmailConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              {gmailConnected && (
                <div className="summary-row">
                  <span className="summary-label">Account Email</span>
                  <span className="summary-value font-mono">{gmailEmail}</span>
                </div>
              )}
              <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
                <button className="btn-undo" onClick={() => showToast('Disconnection mock triggered.', 'info')}>
                  {gmailConnected ? 'Disconnect' : 'Connect Account'}
                </button>
              </div>
            </div>

            {/* Telegram Bot Status */}
            <div className="summary-card" style={{ margin: 0 }}>
              <h2 style={{ marginBottom: 16 }}>Telegram Admin Bot</h2>
              <div className="summary-row">
                <span className="summary-label">Status</span>
                <span className="summary-value" style={{ color: 'var(--accent-resolved)' }}>
                  Connected
                </span>
              </div>
              <div style={{ marginTop: 12, fontSize: '0.8rem', color: 'var(--muted)' }}>
                <strong>Commands:</strong> <code>START</code> · <code>STOP</code> · <code>/status</code> · <code>/help</code>
              </div>
            </div>

            {/* Policy Proposals */}
            <div className="summary-card" style={{ margin: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <h2 style={{ margin: 0 }}>Policy Amendment Proposals</h2>
                <button
                  id="btn-refresh-proposals"
                  onClick={fetchProposals}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}
                >
                  <RefreshCw size={16} />
                </button>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: 16 }}>
                Auto-generated when 3+ human overrides accumulate. Approve to update live policy &amp; re-index RAG.
              </p>

              {proposalsLoading ? (
                <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)' }}>
                  <div className="loading-spinner" style={{ margin: '0 auto 8px' }} />
                  Loading proposals…
                </div>
              ) : proposals.length === 0 ? (
                <div style={{
                  textAlign: 'center', padding: '32px', borderRadius: '12px',
                  background: 'var(--bg)', border: '1px dashed var(--border)',
                }}>
                  <ShieldCheck size={32} style={{ margin: '0 auto 8px', display: 'block' }} color="var(--accent-resolved)" />
                  <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>No pending proposals — policy is up to date.</div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {proposals.map(p => (
                    <div key={p.id} style={{
                      padding: '16px', borderRadius: '12px',
                      border: p.status === 'pending' ? '1px solid rgba(99,102,241,0.4)' : '1px solid var(--border)',
                      background: p.status === 'pending' ? 'rgba(99,102,241,0.05)' : 'var(--bg)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
                        <div>
                          <span style={{
                            fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase',
                            padding: '2px 8px', borderRadius: '4px',
                            background: p.status === 'pending' ? '#6366f1' : p.status === 'approved' ? '#22c55e' : '#ef4444',
                            color: '#fff', marginRight: '8px',
                          }}>
                            {p.status}
                          </span>
                          <strong style={{ fontSize: '0.9rem' }}>{p.title}</strong>
                        </div>
                        <span style={{ fontSize: '0.72rem', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                          {new Date(p.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: '12px' }}>{p.reasoning}</p>
                      {p.proposed_diff && (
                        <pre style={{
                          fontSize: '0.75rem', background: '#0f172a', color: '#a5f3fc',
                          padding: '10px', borderRadius: '8px', marginBottom: '12px',
                          overflowX: 'auto', whiteSpace: 'pre-wrap',
                        }}>
                          {p.proposed_diff}
                        </pre>
                      )}
                      {p.status === 'pending' && (
                        <div style={{ display: 'flex', gap: '10px' }}>
                          <button
                            id={`btn-approve-proposal-${p.id}`}
                            className="btn-primary"
                            style={{ flex: 1, margin: 0, justifyContent: 'center', fontSize: '0.82rem', padding: '8px' }}
                            onClick={() => handleProposal(p.id, 'approve')}
                          >
                            ✓ Approve &amp; Update Policy
                          </button>
                          <button
                            id={`btn-reject-proposal-${p.id}`}
                            className="btn-undo"
                            style={{ margin: 0, fontSize: '0.82rem', padding: '8px 16px' }}
                            onClick={() => handleProposal(p.id, 'reject')}
                          >
                            ✗ Reject
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : activeTab === 'broadcasts' ? (
        <BroadcastTab businessId={selectedBusiness} showToast={showToast} />
      ) : (
        <div className="dashboard">
          {/* LEFT — Inbox */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button 
                  onClick={() => { fetchDemoEmails(); checkGmailStatus(); }}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: '4px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--muted)', borderRadius: '4px'
                  }}
                  title="Refresh inbox"
                >
                  <RefreshCw size={14} className={loadingEmails ? 'spin' : ''} />
                </button>
                <span className="text-xs" style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>
                  {displayEmails.length} emails
                </span>
                {gmailConnected && activeTab === 'inbox' && (
                  <button className="btn-undo" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={triggerPoll}>
                    Check now
                  </button>
                )}
              </div>
            </div>
            <div className="panel-body" style={{ padding: '8px' }}>
              {loadingEmails ? (
                <div className="empty-state">
                  <div className="loading-spinner" />
                  <div className="empty-sub">Loading emails…</div>
                </div>
              ) : displayEmails.length === 0 ? (
                <div className="empty-state">
                  <Inbox size={48} className="icon" />
                  <div className="empty-title">Nothing to show</div>
                  {activeTab === 'inbox' && (
                    <button className="btn-undo" style={{ marginTop: 8 }} onClick={fetchDemoEmails}>
                      Load sample emails
                    </button>
                  )}
                </div>
              ) : (
                <EmailList
                  emails={displayEmails}
                  selectedId={selectedId}
                  results={results}
                  onSelect={id => setSelectedId(id)}
                />
              )}
            </div>
          </div>

          {/* MIDDLE — Email Detail */}
          <div className="panel">
            {selectedEmail ? (
              <EmailDetail email={selectedEmail} processed={!!selectedResult} />
            ) : (
              <div className="empty-state">
                <Mail size={48} className="icon" />
                <div className="empty-title">Select an email to see the details</div>
              </div>
            )}
          </div>

          {/* RIGHT — Action log + reply */}
          <div className="panel" style={{ borderRight: 'none' }}>
            {loading ? (
              <div className="empty-state">
                <div className="loading-spinner" style={{ width: 40, height: 40, marginBottom: 16 }} />
                <div className="empty-title">Analysing email with AI...</div>
                <div className="empty-sub" style={{ marginTop: 8 }}>
                  Extracting details, checking policies, and drafting a reply.
                </div>
              </div>
            ) : selectedResult ? (
              <ActionPanel
                result={selectedResult}
                isApproved={selectedEmail.approved}
                onApprove={() => approveAndSend(selectedId)}
                onUndo={() => undoAction(selectedId)}
              />
            ) : (
              <div className="empty-state">
                <Sparkles size={48} className="icon" />
                <div className="empty-title">Ready for AI Analysis</div>
                <button
                  className="btn-primary"
                  style={{ marginTop: 16, opacity: selectedEmail ? 1 : 0.5, cursor: selectedEmail ? 'pointer' : 'not-allowed' }}
                  onClick={() => selectedEmail && processEmail(selectedEmail)}
                  disabled={!selectedEmail}
                >
                  Analyse with AI
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
