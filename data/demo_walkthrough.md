# SupportAI — Demo Walkthrough Script
**Version 1.0 | Phase 9 Complete**

---

## Before You Start (1 minute checklist)

- [ ] Backend running: `cd backend && venv\Scripts\python -m uvicorn main:app --reload --port 8000`
- [ ] Frontend running: `cd frontend && npm run dev`
- [ ] `GEMINI_API_KEY` is filled in `.env`
- [ ] Open browser to `http://localhost:5173`

---

## Showcase Case 1 — Wrong Item → Refund *(~90 seconds)*

**Email to use:** *Sarah Mitchell — "Wrong item received — Order ORD-1001"*

**What you say:**
> "Sarah ordered a Wireless Keyboard but received a USB Hub instead. She's attached her receipt. Watch what the AI does."

**Steps:**
1. Click **Sarah Mitchell** in the inbox (left panel)
2. Middle panel shows her email body + the attachment chip `📎 receipt_ORD1001.png`
3. Click **🤖 Analyse with AI**
4. Watch the processing banner — *"Running AI pipeline — OCR → Match → Decide → Execute…"*
5. Right panel fills with the action log:
   - 🔍 **Document Read** — extracted 700 chars from receipt
   - 🔗 **Order Matched** — ORD-1001, Wireless Keyboard, $89.99
   - 🧠 **Decision Made** — REFUND — customer received wrong item, within 30-day window
   - ⚡ **Action Taken** — Full refund of $89.99 approved, DB updated to "refunded"
   - ✉️ **Reply Drafted** — branded HTML email ready

**What you say:**
> "The AI read the receipt, matched the order, checked our return policy, issued the refund in the database, generated a PDF confirmation, and drafted this email — all without human input."

6. Scroll the reply preview — show the dark header, order summary card, timeline
7. Click **✅ Approve & Send**

---

## Showcase Case 2 — Invoice Amount Wrong → Reissue *(~60 seconds)*

**Email to use:** *Priya Sharma — "Invoice amount is wrong — ORD-1012"*

**What you say:**
> "Priya was charged $749.99 but the agreed price was $649.99. She's attached the incorrect invoice."

**Steps:**
1. Click **Priya Sharma** in inbox
2. Show the invoice attachment chip: `📎 invoice_ORD1012.png`
3. Click **Analyse with AI**
4. Action log shows:
   - OCR extracts: *ORD-1012, 4K Monitor, $749.99*
   - Matches DB record: *$649.99* — detects the $100 discrepancy
   - Decision: **REISSUE INVOICE**
   - Action: corrected invoice PDF generated
5. Show the reply preview with the corrected invoice amount

**What you say:**
> "It found the mismatch, created a corrected invoice, and the reply tells Priya the refund of $100 will appear in 5 days."

---

## Showcase Case 3 — Escalation (No Order Found) *(~45 seconds)*

**Email to use:** *Nina Clarke — "Refund for cancelled order ORD-9999"*

**What you say:**
> "Nina is claiming a refund for ORD-9999. Let's see what happens when the order doesn't exist."

**Steps:**
1. Click **Nina Clarke** in inbox
2. Click **Analyse with AI**
3. Action log shows:
   - 🔍 No attachment — reading email body
   - 🔗 Order `ORD-9999` **not found** in system
   - 🧠 Decision: **ESCALATE** — order ID cannot be verified
   - ✉️ Reply drafted: *"Our team is on it"* message, no automated action taken

**What you say:**
> "When the AI isn't confident — order not found, or the situation is ambiguous — it escalates instead of guessing. No refund is issued. A human reviews it."

---

## Showcase Case 4 — Technical Issue → Escalate *(~30 seconds)*

**Email to use:** *David Chen — "App keeps crashing on startup"*

**What you say:**
> "David has a technical problem — no order involved at all."

**Steps:**
1. Click **David Chen** in inbox
2. No attachment chip shown — purely a text email
3. Click **Analyse with AI**
4. Decision: **ESCALATE** — technical issue, outside refund policy scope

**What you say:**
> "Technical support emails are out of scope for automated resolution. The AI recognises this and escalates immediately without wasting any action."

---

## Undo Demo *(optional, 20 seconds)*

After any refund/replace case:
1. Click **↩ Undo** in the action panel
2. Toast: *"Action reversed — order restored"*
3. Click on the email again — it's back to unprocessed state
4. The order in the DB is back to `delivered`

---

## Gmail Integration *(if configured)*

1. Click **📬 Connect Gmail** in the navbar
2. Complete Google OAuth in the popup (secondary account only)
3. Navbar shows **📬 Gmail Connected** in green
4. Live Gmail emails appear at the top of the inbox labelled **📬 Live**
5. Full pipeline runs identically — replies saved as **Gmail Drafts only**

---

## Key Points to Emphasise

| Point | What to say |
|-------|-------------|
| **AI does the work** | The DB was actually updated. The PDF was actually generated. |
| **Draft-only for Gmail** | Nothing auto-sends. You review, then Approve. |
| **No confidence scores** | Plain English log — "Matched to order", "Refund issued", not "87% confidence" |
| **Graceful escalation** | Uncertain = escalate, not guess. Errors never crash the system. |
| **Branded emails** | The reply template is production-quality HTML — usable today |

---

## Troubleshooting Quick Reference

| Symptom | Fix |
|---------|-----|
| "0 emails" in inbox | Check backend is running on port 8000 |
| "Gemini not configured" | Add `GEMINI_API_KEY` to `.env` and restart backend |
| OCR reads nothing | Text sidecar `.txt` file is used as fallback — still works |
| Action log shows "escalate" on everything | Gemini API key issue — check API console quota |
| Gmail auth fails | Check `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` in `.env` |
