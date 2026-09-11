function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function EmailList({ emails, selectedId, results, onSelect }) {
  return (
    <div>
      {emails.map(email => {
        const result = results[email.id]
        let statusClass = 'pending'
        
        if (result || email.processed) {
          const action = result ? result.action : email.action
          if (action === 'escalate') {
            statusClass = 'escalated'
          } else if (action) {
            statusClass = 'resolved'
          }
        }

        const isActive = email.id === selectedId

        return (
          <div
            key={email.id}
            className={`email-item${isActive ? ' active' : ''}`}
            onClick={() => onSelect(email.id)}
            id={`email-item-${email.id}`}
          >
            <div className="email-sender-row">
              <div className={`status-dot ${statusClass}`} />
              <span className="email-sender">{email.from_name}</span>
              {email.source === 'gmail' && (
                <span style={{ fontSize: '0.65rem', marginLeft: 'auto', background: 'var(--accent-resolved)', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 600, letterSpacing: '0.02em', textTransform: 'uppercase' }}>Live</span>
              )}
            </div>
            <div className="email-subject">{email.subject}</div>
            <div className="email-preview">{(email.body || '').slice(0, 80)}…</div>
          </div>
        )

      })}
    </div>
  )
}
