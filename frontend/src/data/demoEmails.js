/**
 * Placeholder demo email list — replaced with real data in Phase 1.
 * Used so the React app renders without the backend.
 */
export const DEMO_EMAILS = [
  {
    id: 'email-001',
    from_name: 'Sarah Mitchell',
    from_email: 'sarah.mitchell@example.com',
    subject: 'Wrong item received — Order #ORD-1042',
    body: "Hi, I placed an order for a Wireless Keyboard (Order #ORD-1042) but received a USB Hub instead. This is very frustrating. I've attached my receipt. Can you please arrange a replacement or refund?",
    received_at: new Date(Date.now() - 25 * 60000).toISOString(),
    source: 'demo',
    attachment_filename: 'receipt_ORD1042.png',
  },
  {
    id: 'email-002',
    from_name: 'James Okafor',
    from_email: 'james.ok@example.com',
    subject: 'Refund request — damaged product ORD-1055',
    body: "The laptop stand I received (ORD-1055) arrived with a cracked base. I'm requesting a full refund. Please see the attached invoice.",
    received_at: new Date(Date.now() - 60 * 60000).toISOString(),
    source: 'demo',
    attachment_filename: 'invoice_ORD1055.png',
  },
  {
    id: 'email-003',
    from_name: 'Priya Sharma',
    from_email: 'priya.sharma@example.com',
    subject: 'Invoice amount incorrect — ORD-1031',
    body: "Hello, I received invoice #ORD-1031 but the amount charged ($189.99) does not match what I agreed to ($149.99). Could you please reissue a corrected invoice?",
    received_at: new Date(Date.now() - 2 * 3600000).toISOString(),
    source: 'demo',
    attachment_filename: 'invoice_ORD1031.png',
  },
  {
    id: 'email-004',
    from_name: 'David Chen',
    from_email: 'd.chen@example.com',
    subject: 'App keeps crashing on startup',
    body: "I downloaded your desktop app last week and it crashes every time I open it. I'm on Windows 11. I haven't been able to use it at all. Completely unusable.",
    received_at: new Date(Date.now() - 3 * 3600000).toISOString(),
    source: 'demo',
    attachment_filename: null,
  },
  {
    id: 'email-005',
    from_name: 'Emily Watson',
    from_email: 'emily.w@example.com',
    subject: 'Where is my order? ORD-1088',
    body: "My order ORD-1088 was supposed to arrive 3 days ago. Tracking shows it's still in transit. Can someone look into this?",
    received_at: new Date(Date.now() - 5 * 3600000).toISOString(),
    source: 'demo',
    attachment_filename: null,
  },
]
