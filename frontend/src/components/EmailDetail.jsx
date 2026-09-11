import { Paperclip } from 'lucide-react'

function MetaRow({ label, value }) {
  return (
    <div style={{ display: 'flex', gap: '16px', marginBottom: '8px' }}>
      <span className="text-muted" style={{ width: '64px', fontSize: '0.85rem' }}>{label}</span>
      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

function formatDate(iso) {
  return new Date(iso).toLocaleString([], {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

export default function EmailDetail({ email, onProcess, processed, loading }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <span className="panel-title">Message</span>
        <span className="text-muted" style={{ fontSize: '0.8rem' }}>
          {email.source === 'gmail' ? 'Live Gmail' : 'Demo data'}
        </span>
      </div>

      <div className="panel-body" style={{ padding: '24px' }}>
        <div className="email-detail-header">
          <div className="email-detail-subject">{email.subject}</div>
          <div className="email-detail-meta">
            <MetaRow label="From" value={`${email.from_name} <${email.from_email}>`} />
            <MetaRow label="Date" value={formatDate(email.received_at)} />
          </div>
        </div>

        <div className="email-detail-body">{email.body}</div>

        {email.attachment_filename && (
          <div className="attachment-card">
            <span className="attachment-name">
              <Paperclip size={16} className="text-muted" /> 
              {email.attachment_filename}
            </span>
          </div>
        )}
      </div>

    </div>
  )
}
