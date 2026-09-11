import { Inbox, CheckCircle2, Zap, Settings, Mail, ChevronDown, Building2 } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

const BUSINESSES = [
  { id: 'biz_tech',    label: 'TechGadgets Inc.' },
  { id: 'biz_apparel', label: 'StyleHub Apparel'  },
]

export default function Navbar({
  brandConfig, totalEmails, processedCount,
  gmailConnected, gmailEmail,
  activeTab, onTabChange,
  selectedBusiness, onBusinessChange,
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const current = BUSINESSES.find(b => b.id === selectedBusiness) || BUSINESSES[0]

  // Close on outside click
  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <nav className="navbar">
      {/* Left: Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginRight: '20px' }}>
        {brandConfig?.brand_logo_url && (
          <img src={brandConfig.brand_logo_url} alt="" style={{ height: '22px', width: 'auto' }} />
        )}
        <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.01em' }}>
          {brandConfig?.brand_name || 'SupportAI'}
        </span>

        {/* Divider */}
        <span style={{ width: 1, height: 18, background: 'var(--border-strong)', margin: '0 4px' }} />

        {/* Business Switcher — inline, minimal */}
        <div ref={ref} style={{ position: 'relative' }}>
          <button
            id="business-switcher"
            onClick={() => setOpen(o => !o)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px 4px 8px',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              background: open ? 'var(--bg-paper)' : 'transparent',
              color: 'var(--ink)',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-paper)'}
            onMouseLeave={e => { if (!open) e.currentTarget.style.background = 'transparent' }}
          >
            <Building2 size={13} strokeWidth={2} color="var(--muted)" />
            <span>{current.label}</span>
            <ChevronDown
              size={12}
              strokeWidth={2.5}
              color="var(--muted)"
              style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
            />
          </button>

          {open && (
            <div style={{
              position: 'absolute',
              top: 'calc(100% + 6px)',
              left: 0,
              zIndex: 1000,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              boxShadow: '0 6px 24px rgba(0,0,0,0.08)',
              minWidth: '190px',
              overflow: 'hidden',
              padding: '4px',
            }}>
              {BUSINESSES.map(biz => {
                const isActive = biz.id === selectedBusiness
                return (
                  <button
                    key={biz.id}
                    id={`switch-${biz.id}`}
                    onClick={() => { onBusinessChange(biz.id); setOpen(false) }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: '6px',
                      border: 'none',
                      cursor: 'pointer',
                      background: isActive ? 'var(--bg-paper)' : 'transparent',
                      color: 'var(--ink)',
                      fontSize: '0.85rem',
                      fontWeight: isActive ? 600 : 400,
                      textAlign: 'left',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--bg-paper)' }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
                  >
                    {/* Active indicator dot */}
                    <span style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: isActive ? 'var(--accent-resolved)' : 'var(--border-strong)',
                      flexShrink: 0,
                      transition: 'background 0.15s',
                    }} />
                    <span style={{ flex: 1 }}>{biz.label}</span>
                    {isActive && (
                      <span style={{
                        fontSize: '0.72rem',
                        fontFamily: 'IBM Plex Mono, monospace',
                        color: 'var(--muted)',
                        fontWeight: 400,
                      }}>
                        active
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Center: Nav pills */}
      <div className="navbar-nav" style={{ flex: 1, justifyContent: 'center' }}>
        <button className={`nav-pill ${activeTab === 'inbox' ? 'active' : ''}`} onClick={() => onTabChange('inbox')}>
          <Inbox size={16} /> Inbox
        </button>
        <button className={`nav-pill ${activeTab === 'resolved' ? 'active' : ''}`} onClick={() => onTabChange('resolved')}>
          <CheckCircle2 size={16} /> Resolved
        </button>
        <button className={`nav-pill ${activeTab === 'escalated' ? 'active' : ''}`} onClick={() => onTabChange('escalated')}>
          <Zap size={16} /> Escalated
        </button>
        <button className={`nav-pill ${activeTab === 'broadcasts' ? 'active' : ''}`} onClick={() => onTabChange('broadcasts')}>
          <Zap size={16} /> Broadcasts
        </button>
        <button className={`nav-pill ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => onTabChange('settings')}>
          <Settings size={16} /> Settings
        </button>
      </div>

      {/* Right: Status */}
      <div className="navbar-actions">
        <span style={{ fontSize: '0.8rem', color: 'var(--muted)', fontFamily: 'IBM Plex Mono, monospace' }}>
          {processedCount}/{totalEmails}
        </span>
        {gmailConnected && (
          <div className="btn-connect connected">
            <Mail size={14} />
            {gmailEmail || 'Gmail'}
          </div>
        )}
      </div>
    </nav>
  )
}
