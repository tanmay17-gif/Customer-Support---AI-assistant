"""
Telegram Admin Bot Service

- START/STOP monitoring commands (text or /start /stop)
- Real-time event notifications
- 5-minute periodic summaries
- Inline APPROVE/REJECT for escalated cases
- Catch-up summary when resuming after STOP
- Professional messages — no emoji clutter

IMPORTANT: STOP only pauses Telegram notifications.
The Customer Support system continues working in the background.
"""
import asyncio
import hashlib
import json
from datetime import datetime
from typing import Optional
from loguru import logger

from app.core.config import settings

# ─── Singleton ────────────────────────────────────────────────────────────────
_bot_app = None
_summary_task: Optional[asyncio.Task] = None

# Short callback_data map: Telegram limits callback_data to 64 bytes.
# We store short 12-char keys that map to full email IDs.
_callback_map: dict[str, str] = {}   # short_key -> email_id


def _short_key(email_id: str) -> str:
    """Create a stable 12-char key safe for Telegram callback_data."""
    return hashlib.md5(email_id.encode()).hexdigest()[:12]


def _register_email(email_id: str) -> str:
    key = _short_key(email_id)
    _callback_map[key] = email_id
    return key


def _resolve_key(key: str) -> Optional[str]:
    return _callback_map.get(key)


# ─── DB Helpers ───────────────────────────────────────────────────────────────

async def _get_state():
    from app.core.database import AsyncSessionLocal
    from app.models.telegram_state import TelegramState
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TelegramState).where(TelegramState.id == 1))
        state = result.scalar_one_or_none()
        if not state:
            state = TelegramState(id=1, monitoring_active=False)
            db.add(state)
            await db.commit()
            await db.refresh(state)
        return state


async def _save_state(**kwargs):
    from app.core.database import AsyncSessionLocal
    from app.models.telegram_state import TelegramState
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TelegramState).where(TelegramState.id == 1))
        state = result.scalar_one_or_none()
        if not state:
            state = TelegramState(id=1)
            db.add(state)
        for k, v in kwargs.items():
            setattr(state, k, v)
        state.updated_at = datetime.utcnow()
        await db.commit()


async def increment_counter(counter: str, by: int = 1):
    from app.core.database import AsyncSessionLocal
    from app.models.telegram_state import TelegramState
    from sqlalchemy import update
    async with AsyncSessionLocal() as db:
        col = TelegramState.__table__.c.get(counter)
        if col is None:
            return
        await db.execute(
            update(TelegramState)
            .where(TelegramState.id == 1)
            .values(**{counter: col + by})
        )
        await db.commit()


async def _count_pending_approvals() -> int:
    """Count only real customer escalations, not system emails."""
    from app.core.database import AsyncSessionLocal
    from app.models.processing_record import ProcessingRecord
    from app.models.email import EmailRecord
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ProcessingRecord)
            .join(EmailRecord, ProcessingRecord.email_id == EmailRecord.id)
            .where(
                ProcessingRecord.action == "escalate",
                ProcessingRecord.status == "pending",
            )
        )
        res = await db.execute(stmt)
        records = res.scalars().all()
        return len(records)


# ─── Bot Send Helpers ─────────────────────────────────────────────────────────

async def send_message(text: str, reply_markup=None, parse_mode: str = "HTML"):
    """Send to admin only if monitoring is active."""
    global _bot_app
    if _bot_app is None:
        return
    state = await _get_state()
    if not state.chat_id or not state.monitoring_active:
        return
    try:
        await _bot_app.bot.send_message(
            chat_id=state.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


async def _send_direct(chat_id: str, text: str, reply_markup=None, parse_mode: str = "HTML"):
    """Send regardless of monitoring state (for START/STOP confirmations)."""
    global _bot_app
    if _bot_app is None:
        return
    try:
        await _bot_app.bot.send_message(
            chat_id=chat_id, text=text,
            reply_markup=reply_markup, parse_mode=parse_mode,
        )
    except Exception as e:
        logger.warning(f"Telegram direct send failed: {e}")


# ─── Notification Helpers (called from polling pipeline) ──────────────────────

async def notify_email_processed(email_subject: str, action: str, customer: str, 
                                 sent_reply: str = "", audit_score: int = 100, action_log_len: int = 0):
    await increment_counter("emails_analyzed")
    if action in ("refund", "replace", "reissue_invoice", "issue_credit", "answer_query"):
        await increment_counter("auto_resolved")
        await increment_counter("individual_resolved")

    action_labels = {
        "refund": "Refund Processed",
        "replace": "Replacement Arranged",
        "reissue_invoice": "Invoice Reissued",
        "issue_credit": "Credit Issued",
        "request_info": "Info Requested from Customer",
        "answer_query": "Query Answered from Database",
    }
    label = action_labels.get(action, action.upper())

    msg = (
        f"<b>✅ Auditor Approved (Risk Score: {audit_score}/100)</b>\n"
        f"<i>🔗 SHA-256 Evidence Chain Intact ({action_log_len} events)</i>\n\n"
        f"<b>Customer:</b> {customer}\n"
        f"<b>Subject:</b> {email_subject[:80]}\n"
        f"<b>Action Executed:</b> {label}\n"
    )
    if sent_reply:
        msg += f"\n<b>Reply Sent:</b>\n<i>{sent_reply[:300]}...</i>"

    await send_message(msg)


async def notify_escalation(email_id: str, email_subject: str, customer_name: str,
                            customer_email: str, draft_reply: str, reason: str,
                            dossier: dict = None, audit_score: int = 100, action_log_len: int = 0):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    key = _register_email(email_id)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("APPROVE", callback_data=f"A:{key}"),
            InlineKeyboardButton("REJECT",  callback_data=f"R:{key}"),
        ]
    ])
    await increment_counter("escalated")
    await increment_counter("pending_approvals")
    
    sentiment = dossier.get("sentiment", "Neutral") if dossier else "Neutral"
    recommended = dossier.get("recommended_action_description", "Manual Review") if dossier else "Manual Review"
    
    msg = (
        f"<b>⚠️ Escalation Dossier (Risk Score: {audit_score}/100)</b>\n"
        f"<i>🔗 SHA-256 Evidence Chain Intact ({action_log_len} events)</i>\n\n"
        f"<b>Customer:</b> {customer_name} &lt;{customer_email}&gt;\n"
        f"<b>Sentiment:</b> {sentiment}\n"
        f"<b>Subject:</b> {email_subject[:80]}\n\n"
        f"<b>Escalation Reason:</b>\n{reason[:120]}\n\n"
        f"<b>Recommended Action:</b>\n{recommended}\n\n"
        f"<b>AI Draft Response:</b>\n"
        f"<i>{draft_reply[:300]}...</i>"
    )
    
    await send_message(msg, reply_markup=keyboard)


async def notify_cluster(cluster_id: str, root_cause: str, count: int):
    await increment_counter("common_issues_detected")
    await increment_counter("common_responses_sent", count)
    await increment_counter("auto_resolved", count)
    await send_message(
        f"<b>Common Issue Resolved Automatically</b>\n\n"
        f"Issue: {root_cause}\n"
        f"Customers affected: {count}\n"
        f"Action: Broadcast response generated and sent\n"
        f"Status: Resolved"
    )


async def notify_invoice(customer: str, issue: str, invoice_id: str, amount: str):
    await increment_counter("invoices_generated")
    await send_message(
        f"<b>Invoice Generated</b>\n\n"
        f"Customer: {customer}\n"
        f"Issue: {issue}\n"
        f"Invoice ID: {invoice_id}\n"
        f"Amount: {amount}\n"
        f"Status: Generated"
    )


async def notify_error(error: str, action_taken: str):
    await increment_counter("errors")
    await send_message(
        f"<b>System Alert</b>\n\n"
        f"Error: {error[:200]}\n"
        f"Action taken: {action_taken}"
    )


# ─── Command Handlers ─────────────────────────────────────────────────────────

def _is_authorized(chat_id: str) -> bool:
    if not settings.TELEGRAM_ADMIN_CHAT_ID:
        return True  # No restriction set — allow all
    return chat_id == settings.TELEGRAM_ADMIN_CHAT_ID


async def cmd_start(update, context):
    chat_id = str(update.effective_chat.id)
    if not _is_authorized(chat_id):
        await update.message.reply_text("Unauthorized. This bot is restricted to the system administrator.")
        return

    state = await _get_state()
    was_paused = not state.monitoring_active and state.paused_since is not None
    paused_since = state.paused_since

    # Save counts before reset
    saved = {
        "emails_analyzed": state.emails_analyzed,
        "common_issues_detected": state.common_issues_detected,
        "common_responses_sent": state.common_responses_sent,
        "individual_resolved": state.individual_resolved,
        "escalated": state.escalated,
        "invoices_generated": state.invoices_generated,
        "errors": state.errors,
    }

    # Activate monitoring and reset period counters
    await _save_state(
        chat_id=chat_id, monitoring_active=True, paused_since=None,
        emails_analyzed=0, auto_resolved=0, common_issues_detected=0,
        common_responses_sent=0, individual_resolved=0, escalated=0,
        pending_approvals=0, invoices_generated=0, errors=0,
    )

    pending = await _count_pending_approvals()

    if was_paused and paused_since:
        pause_dur = datetime.utcnow() - paused_since.replace(tzinfo=None)
        mins = int(pause_dur.total_seconds() // 60)
        msg = (
            f"<b>Monitoring Resumed</b>\n\n"
            f"Updates were paused for: {mins} minutes\n\n"
            f"<b>Activity during paused period:</b>\n"
            f"Emails analyzed: {saved['emails_analyzed']}\n"
            f"Common issues detected: {saved['common_issues_detected']}\n"
            f"Broadcast responses sent: {saved['common_responses_sent']} customers\n"
            f"Individual issues resolved: {saved['individual_resolved']}\n"
            f"New escalations: {saved['escalated']}\n"
            f"Pending Admin approvals: {pending}\n"
            f"Invoices generated: {saved['invoices_generated']}\n"
            f"Errors: {saved['errors']}\n\n"
            f"<b>System Status:</b> RUNNING\n"
            f"Live monitoring has resumed. Send STOP to pause."
        )
    else:
        msg = (
            f"<b>Customer Support Monitoring Started</b>\n\n"
            f"System Status: RUNNING\n"
            f"Pending approvals: {pending}\n\n"
            f"You will receive:\n"
            f"  - Immediate alerts for escalations requiring approval\n"
            f"  - Auto-resolution notifications\n"
            f"  - 5-minute activity summaries\n\n"
            f"Commands: START | STOP | /status | /pending | /help\n\n"
            f"Send STOP to pause Telegram updates (system keeps working)."
        )

    await _send_direct(chat_id, msg)

    # Restart 5-minute summary loop if needed
    global _summary_task
    if _summary_task is None or _summary_task.done():
        _summary_task = asyncio.create_task(_five_minute_summary_loop())


async def cmd_stop(update, context):
    chat_id = str(update.effective_chat.id)
    if not _is_authorized(chat_id):
        await update.message.reply_text("Unauthorized.")
        return

    await _save_state(monitoring_active=False, paused_since=datetime.utcnow())
    await _send_direct(
        chat_id,
        "<b>Admin Updates Paused</b>\n\n"
        "The Customer Support Assistant continues working in the background.\n"
        "All activities are being logged.\n\n"
        "System Status: RUNNING (notifications paused)\n\n"
        "Send START anytime to resume monitoring and receive a summary "
        "of everything completed during this period."
    )


async def cmd_status(update, context):
    chat_id = str(update.effective_chat.id)
    if not _is_authorized(chat_id):
        await update.message.reply_text("Unauthorized.")
        return

    from app.core.database import AsyncSessionLocal
    from app.models.processing_record import ProcessingRecord
    from sqlalchemy import select, func
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(ProcessingRecord))).scalar()

    pending = await _count_pending_approvals()
    state = await _get_state()
    monitoring = "ACTIVE" if state.monitoring_active else "PAUSED (notifications only)"

    await _send_direct(
        chat_id,
        f"<b>System Status</b>\n\n"
        f"System: RUNNING\n"
        f"Telegram Monitoring: {monitoring}\n\n"
        f"Total tickets processed: {total}\n"
        f"Pending escalations (awaiting approval): {pending}\n\n"
        f"Commands: START | STOP | /status | /pending | /help"
    )


async def cmd_pending(update, context):
    """List current pending escalations."""
    chat_id = str(update.effective_chat.id)
    if not _is_authorized(chat_id):
        await update.message.reply_text("Unauthorized.")
        return

    from app.core.database import AsyncSessionLocal
    from app.models.processing_record import ProcessingRecord
    from app.models.email import EmailRecord
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ProcessingRecord, EmailRecord)
            .join(EmailRecord, ProcessingRecord.email_id == EmailRecord.id)
            .where(ProcessingRecord.action == "escalate", ProcessingRecord.status == "pending")
        )
        res = await db.execute(stmt)
        rows = res.all()

    if not rows:
        await _send_direct(chat_id, "<b>Pending Escalations</b>\n\nNo pending escalations. All clear.")
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # Send individual verify buttons for each pending escalation
    for proc, email in rows[:5]:
        key = _register_email(email.id)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("VERIFY", callback_data=f"V:{key}")
        ]])
        await _send_direct(
            chat_id,
            f"<b>Pending:</b> {email.from_name}\n"
            f"Subject: {email.subject[:80]}",
            reply_markup=keyboard
        )


async def cmd_help(update, context):
    chat_id = str(update.effective_chat.id)
    await _send_direct(
        chat_id,
        "<b>CS Admin Bot — Commands</b>\n\n"
        "<b>START</b> — Resume monitoring. If previously paused, shows catch-up summary.\n"
        "<b>STOP</b> — Pause Telegram updates only. Support system keeps running.\n"
        "<b>/status</b> — View live system status and ticket counts.\n"
        "<b>/pending</b> — List all escalated cases waiting for your approval.\n"
        "<b>/help</b> — Show this message.\n\n"
        "<b>Note:</b> Use inline APPROVE / REJECT buttons to action escalated cases directly in chat."
    )


async def handle_text(update, context):
    text = (update.message.text or "").strip().upper()
    if text in ("START", "/START"):
        await cmd_start(update, context)
    elif text in ("STOP", "/STOP"):
        await cmd_stop(update, context)
    else:
        await update.message.reply_text(
            "Available commands: START | STOP | /status | /pending | /help",
            parse_mode="HTML"
        )


async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    # ── Mark as Read: delete the summary message ────────────────────────────
    if data == "SUMMARY:READ":
        global _last_summary_message_id, _summary_is_read
        try:
            await query.delete_message()
        except Exception:
            pass
        _last_summary_message_id = None
        _summary_is_read = True
        return

    if ":" not in data:
        return

    action_type, key = data.split(":", 1)
    email_id = _resolve_key(key)

    if not email_id:
        await query.edit_message_text("Session expired. Use /pending to re-list escalations.")
        return

    from app.core.database import AsyncSessionLocal
    from app.models.processing_record import ProcessingRecord
    from app.models.email import EmailRecord
    from app.services import gmail_service

    async with AsyncSessionLocal() as db:
        record = await db.get(ProcessingRecord, email_id)
        if not record:
            await query.edit_message_text("Case not found in database.")
            return

        email_rec = await db.get(EmailRecord, email_id)

        if action_type == "V":
            # Show the dossier and approve/reject buttons
            result_data = json.loads(record.result_json)
            await query.delete_message()  # Remove the small verify message
            await notify_escalation(
                email_id=email_id,
                email_subject=email_rec.subject if email_rec else "N/A",
                customer_name=email_rec.from_name if email_rec else "N/A",
                customer_email=email_rec.from_email if email_rec else "N/A",
                draft_reply=result_data.get("drafted_reply_text", ""),
                reason=result_data.get("escalation_reason", ""),
                dossier=result_data.get("escalation_dossier"),
                audit_score=result_data.get("audit_score", 100),
                action_log_len=len(result_data.get("action_log", []))
            )
            return

        if action_type == "A":
            record.status = "approved"
            await db.commit()

            sent = False
            if email_rec and gmail_service.is_authenticated():
                try:
                    result_data = json.loads(record.result_json)
                    sent = gmail_service.send_email(
                        to_email=email_rec.from_email,
                        subject=email_rec.subject,
                        html_body=result_data.get("drafted_reply_html", ""),
                        message_id=email_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to send approved email: {e}")

            await query.edit_message_text(
                f"<b>Approved and Sent</b>\n\n"
                f"Customer: {email_rec.from_name if email_rec else email_id}\n"
                f"Reply sent: {'Yes' if sent else 'No (Gmail not connected)'}\n"
                f"Status: Resolved",
                parse_mode="HTML"
            )

        elif action_type == "R":
            record.status = "rejected"
            await db.commit()
            await query.edit_message_text(
                f"<b>Rejected</b>\n\n"
                f"Response was not sent.\n"
                f"Case remains pending for manual handling.",
                parse_mode="HTML"
            )


# ─── 5-Minute Summary Loop ────────────────────────────────────────────────────

# Track the last live summary message so we can edit instead of spamming
_last_summary_message_id: Optional[int] = None
_summary_is_read: bool = True   # True = no live unread summary exists


def _build_summary_text(state, pending: int, updated_at: str) -> str:
    return (
        f"<b>Activity Dashboard</b>\n"
        f"<i>Live — updates every 5 min until marked read</i>\n\n"
        f"Tickets processed: {state.emails_analyzed}\n"
        f"Auto-resolved: {state.auto_resolved}\n"
        f"Common issue clusters: {state.common_issues_detected}\n"
        f"Broadcast replies sent: {state.common_responses_sent}\n"
        f"Individual resolved: {state.individual_resolved}\n"
        f"Escalated: {state.escalated}\n"
        f"Awaiting your approval: {pending}\n"
        f"Invoices generated: {state.invoices_generated}\n"
        f"Errors: {state.errors}\n\n"
        f"<i>Last updated: {updated_at} UTC</i>\n"
        f"System: RUNNING"
    )


async def _five_minute_summary_loop():
    global _last_summary_message_id, _summary_is_read, _bot_app
    logger.info("Telegram: smart summary loop started")
    while True:
        await asyncio.sleep(300)
        state = await _get_state()
        if not state.monitoring_active or not state.chat_id:
            continue

        pending = await _count_pending_approvals()
        state = await _get_state()
        updated_at = datetime.utcnow().strftime("%H:%M:%S")
        text = _build_summary_text(state, pending, updated_at)

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Mark as Read", callback_data="SUMMARY:READ")
        ]])

        if _last_summary_message_id and not _summary_is_read:
            # Edit the existing unread message in-place
            try:
                await _bot_app.bot.edit_message_text(
                    chat_id=state.chat_id,
                    message_id=_last_summary_message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                logger.info("Telegram: summary message updated in-place")
                continue
            except Exception as e:
                # Message may have been deleted or too old — fall through to send new
                logger.warning(f"Telegram: could not edit summary, sending new: {e}")
                _last_summary_message_id = None
                _summary_is_read = True

        # Send a fresh summary message
        try:
            msg = await _bot_app.bot.send_message(
                chat_id=state.chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            _last_summary_message_id = msg.message_id
            _summary_is_read = False
            logger.info(f"Telegram: fresh summary sent (msg_id={msg.message_id})")
        except Exception as e:
            logger.warning(f"Telegram: failed to send summary: {e}")


# ─── Bot Startup / Shutdown ───────────────────────────────────────────────────

async def start_bot():
    global _bot_app

    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return

    try:
        from telegram.ext import (
            Application, CommandHandler, MessageHandler,
            CallbackQueryHandler, filters,
        )

        _bot_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        _bot_app.add_handler(CommandHandler("start", cmd_start))
        _bot_app.add_handler(CommandHandler("stop", cmd_stop))
        _bot_app.add_handler(CommandHandler("status", cmd_status))
        _bot_app.add_handler(CommandHandler("pending", cmd_pending))
        _bot_app.add_handler(CommandHandler("help", cmd_help))
        _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        _bot_app.add_handler(CallbackQueryHandler(handle_callback))

        await _bot_app.initialize()
        await _bot_app.start()
        await _bot_app.updater.start_polling(drop_pending_updates=True)

        # Register command menu with Telegram so they appear in the / menu
        from telegram import BotCommand
        await _bot_app.bot.set_my_commands([
            BotCommand("start",   "Resume monitoring and show catch-up summary"),
            BotCommand("stop",    "Pause Telegram updates (system keeps running)"),
            BotCommand("status",  "View live system status"),
            BotCommand("pending", "List escalated cases awaiting approval"),
            BotCommand("help",    "Show all commands"),
        ])

        logger.info("Telegram Admin Bot started.")

        # Restore summary loop if monitoring was already active
        state = await _get_state()
        global _summary_task
        if state.monitoring_active and state.chat_id:
            _summary_task = asyncio.create_task(_five_minute_summary_loop())

    except Exception as e:
        logger.error(f"Telegram bot failed to start: {e}")


async def stop_bot():
    global _bot_app, _summary_task
    if _summary_task and not _summary_task.done():
        _summary_task.cancel()
    if _bot_app:
        try:
            await _bot_app.updater.stop()
            await _bot_app.stop()
            await _bot_app.shutdown()
        except Exception as e:
            logger.warning(f"Telegram bot shutdown error: {e}")
