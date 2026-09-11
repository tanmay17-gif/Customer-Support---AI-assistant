# SupportAI — Autonomous Customer Support Agent

> One AI agent. Multiple businesses. Zero routine tickets handled by humans.

SupportAI is an autonomous customer support system that reads incoming emails, understands them, looks up orders, checks policy, makes a decision, executes it, and sends a branded reply — all without a human touching it. When it genuinely needs human judgment, it sends a full dossier to the admin's Telegram with one-tap approve/reject.

**This is not a chatbot. It is not a help desk with AI suggestions. It is an autonomous support operations system.**

---

## What Makes It Different

| Feature | Typical Support Tool | SupportAI |
|---|---|---|
| Email handling | Human reads & replies | AI reads, decides, acts, sends |
| Fraud detection | None | Dual-agent adversarial auditor |
| Admin interface | Web dashboard | Telegram on your phone |
| Multi-business | Separate systems | One agent, full data isolation |
| Mass incidents | Read 50 identical tickets | Cluster → 1 broadcast reply |
| Audit trail | Activity log | Cryptographic SHA-256 chain |

---

## How It Works — End to End

1. **Email arrives** in your Gmail inbox (via IMAP polling every 30 seconds)
2. **OCR** extracts text from any receipt or invoice attachment
3. **Order matching** finds the customer's order in the database — scoped to their specific business
4. **RAG policy lookup** retrieves the relevant section of your refund/support policy
5. **Decision engine** chooses the right action: refund, replace, reissue invoice, answer query, or escalate
6. **Fraud auditor** (a second independent AI) reviews the decision for receipt tampering, claim frequency, and policy violations — vetoes if anything is wrong
7. **Action execution** — refund processed, replacement arranged, invoice generated, etc.
8. **Branded reply** drafted and sent to the customer automatically
9. **Admin notified** on Telegram with a summary of what was done
10. **Escalations** → admin gets the full dossier on Telegram and taps Approve or Reject

---

## Key Features

### Autonomous Resolution
- Refunds, replacements, invoice reissues, and query answers execute automatically
- Only escalates when it genuinely cannot resolve without human judgment

### Dual-Agent Fraud Detection
- Primary AI makes a decision
- Secondary forensic auditor checks for: tampered receipts (OCR/metadata mismatch), excessive claim history (>3 in 90 days), policy violations, amount discrepancies
- If auditor vetoes → escalated to human, never auto-resolved

### Multi-Tenant Business Isolation
- Manage multiple businesses on one system
- Each business has its own: order database, policy document, ChromaDB RAG collection, email sign-off
- The AI automatically routes each incoming email to the correct business based on order history or content classification
- A customer from Business A can never trigger or see anything from Business B

### Telegram Command Center
- Real-time notifications for every resolved ticket, escalation, and invoice
- `/pending` — see all escalations waiting for review
- `VERIFY` → see full customer dossier → `APPROVE` or `REJECT` in one tap
- Live activity dashboard that edits itself every 5 minutes (no chat spam) with a "Mark as Read" button
- `/status`, `/help` — system overview at any time

### Broadcast Incident Response
- When multiple customers report the same problem, the AI clusters them by root cause
- Admin approves one broadcast reply → sent to all affected customers at once
- Resolves mass incidents without reading individual tickets

### Cryptographic Evidence Chain
- Every pipeline step is SHA-256 hashed and chained
- Tamper-proof audit log: who sent what, what the AI decided, why, what action was taken
- Verifiable end-to-end for compliance and dispute resolution

---

## Project Structure

```
CS_Assistant/
├── backend/                      # FastAPI + Python
│   ├── main.py                   # App entrypoint + lifecycle
│   ├── requirements.txt
│   ├── generate_cluster_test.py  # Seed synthetic data for broadcast testing
│   └── app/
│       ├── core/
│       │   ├── config.py         # All settings loaded from .env
│       │   └── database.py       # SQLite + async SQLAlchemy setup
│       ├── api/
│       │   └── endpoints/
│       │       └── emails.py     # REST API for emails, approve, undo, clusters
│       ├── models/               # SQLAlchemy + Pydantic models
│       ├── services/
│       │   ├── pipeline.py       # Master orchestrator (all 7 steps)
│       │   ├── llm_service.py    # Gemini: extract, decide, audit, draft
│       │   ├── rag_service.py    # ChromaDB per-business policy retrieval
│       │   ├── order_service.py  # Order DB queries (business-scoped)
│       │   ├── action_service.py # Execute: refund, replace, invoice, escalate
│       │   ├── reply_service.py  # Draft + render branded HTML email
│       │   ├── telegram_service.py # Admin bot: commands, notifications, callbacks
│       │   ├── gmail_service.py  # IMAP polling + send + draft
│       │   ├── clustering_service.py # Broadcast: cluster similar escalations
│       │   ├── polling.py        # Background Gmail polling loop
│       │   └── ocr_service.py    # Extract text from receipt images
│       └── templates/
│           └── email_reply.html  # Branded Jinja2 HTML email template
│
├── frontend/                     # React + Vite dashboard
│   └── src/
│       ├── App.jsx               # Root layout + tab routing
│       └── components/
│           ├── EmailList.jsx     # Inbox / Resolved / Escalated tabs
│           ├── EmailDetail.jsx   # Full email view + AI pipeline results
│           ├── ActionPanel.jsx   # Mark resolved, view status
│           ├── StatsBar.jsx      # Live counters
│           └── BroadcastTab.jsx  # Cluster view + broadcast approval
│
├── data/
│   ├── policy/
│   │   ├── techgadgets_policy.txt   # Policy for Business A
│   │   └── stylehub_policy.txt      # Policy for Business B
│   ├── invoices/             # Auto-generated PDF invoices
│   ├── chroma_db/            # Per-business vector stores (auto-created)
│   └── cs_assistant.db       # SQLite database (auto-created)
│
├── .env                      # Your secrets — never commit this
├── .gitignore
├── pyrightconfig.json        # IDE type-checking config
└── README.md
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- A Google Gemini API key ([get one free](https://aistudio.google.com/app/apikey))
- A Gmail account with an App Password (for email polling)
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/CS_Assistant.git
cd CS_Assistant
```

### 2. Set up environment variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini-1.5-flash

# Gmail (IMAP polling — use a dedicated support inbox)
GMAIL_ADDRESS=your_support_email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   # 16-char App Password from Google Account settings

# Telegram admin bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ADMIN_CHAT_ID=your_telegram_chat_id   # Get from https://api.telegram.org/bot<TOKEN>/getUpdates

# Optional — leave blank to use defaults
FRONTEND_URL=http://localhost:5173
DATABASE_URL=sqlite:///./data/cs_assistant.db
```

> **Gmail App Password:** Go to Google Account → Security → 2-Step Verification → App Passwords. Generate one for "Mail". Never use your real Gmail password.

### 3. Set up the backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`

API docs at: `http://localhost:8000/docs`

### 4. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard runs at: `http://localhost:5173`

### 5. Add your business policy documents

Place plain-text policy files in `data/policy/`:

- `techgadgets_policy.txt` — policy for your first business (Business ID: `biz_tech`)
- `stylehub_policy.txt` — policy for your second business (Business ID: `biz_apparel`)

The RAG system indexes these automatically at startup.

### 6. Seed demo orders (optional)

The system ships with sample order data. To add your own, insert rows into the `orders` table with the appropriate `business_id` (`biz_tech` or `biz_apparel`).

### 7. Start the Telegram bot

Send `START` to your bot on Telegram. You'll get a confirmation and the 5-minute activity dashboard will begin.

---

## Using the System

### Via Telegram (primary interface)

| Command | What it does |
|---|---|
| `START` | Begin monitoring, get a catch-up summary of what happened while paused |
| `STOP` | Pause Telegram notifications (system keeps working) |
| `/status` | Current system state and counts |
| `/pending` | List all escalations waiting for review |
| `/help` | All available commands |

**Escalation flow:**
1. AI escalates a ticket → you get a Telegram notification
2. Send `/pending` → tap `VERIFY` on any item
3. See the full customer dossier (order history, AI reasoning, fraud score, draft reply)
4. Tap `APPROVE` → reply is sent to the customer
5. Tap `REJECT` → ticket stays open for manual handling

### Via Dashboard (browser)

Navigate to `http://localhost:5173`:

- **Inbox** — emails still being processed or pending action
- **Resolved** — auto-resolved emails with full pipeline breakdown
- **Escalated** — items requiring human decision (mark as resolved once handled)
- **Broadcasts** — cluster view; click "Find Similar Issues" then approve a broadcast reply

---

## Testing the Broadcast Feature

No need for 20 real email accounts. Run the included test data generator:

```bash
cd backend
venv\Scripts\activate
python generate_cluster_test.py
```

This inserts 5 synthetic identical escalations into the database. Then go to the Broadcasts tab → click "Find Similar Issues" → the AI will cluster them and draft a broadcast reply.

---

## Architecture Overview

```
Gmail Inbox
    │
    ▼ (IMAP poll every 30s)
Polling Service
    │
    ▼
Pipeline Orchestrator
    ├── OCR Service          (extract receipt text)
    ├── LLM: Extract         (parse order ID, amount, item)
    ├── Order Service        (find order — business-scoped)
    ├── RAG Service          (fetch relevant policy — per business)
    ├── LLM: Decide          (choose action)
    ├── LLM: Audit           (fraud & policy check)
    ├── Action Service       (execute refund/replace/etc.)
    └── Reply Service        (draft + send branded email)
         │
         └── Telegram Service (notify admin)
                  │
                  └── Admin approves/rejects escalations
```

---

## Security Notes

- **No credentials in code.** Everything is in `.env` which is gitignored.
- **CORS** is locked to `localhost:5173` and `localhost:3000` only.
- **Telegram bot** only responds to your specific `TELEGRAM_ADMIN_CHAT_ID`.
- **Fraud auditor** independently reviews every decision before money moves.
- **Business isolation** is enforced at the database query level — cross-tenant data access is architecturally impossible.
- **Cryptographic audit chain** — every pipeline step is SHA-256 hashed and chained for tamper-proof logging.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `LLM_MODEL` | Yes | e.g. `gemini-1.5-flash` |
| `GMAIL_ADDRESS` | Yes | Support inbox email address |
| `GMAIL_APP_PASSWORD` | Yes | Gmail App Password (16 chars) |
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | Recommended | Your personal Telegram chat ID |
| `FRONTEND_URL` | No | Default: `http://localhost:5173` |
| `DATABASE_URL` | No | Default: `sqlite:///./data/cs_assistant.db` |
| `DEBUG` | No | Default: `true` |

---

## Built With

- **Backend:** FastAPI, SQLAlchemy (async), SQLite
- **AI:** Google Gemini 1.5 Flash (primary LLM)
- **RAG:** ChromaDB + sentence-transformers
- **Email:** IMAP (Gmail), SMTP, Jinja2 HTML templates
- **Admin Interface:** python-telegram-bot
- **Frontend:** React, Vite
- **PDF Generation:** ReportLab

---

## License

MIT License. Use it, fork it, build on it.
