import asyncio
import json
from loguru import logger
from app.core.database import AsyncSessionLocal
from app.models.processing_record import ProcessingRecord
from app.services import gmail_service
from app.services.pipeline import process_email
from app.models.schemas import IncomingEmail
from app.models.email import EmailRecord
from app.services import telegram_service

async def _poll_iteration():
    if not gmail_service.is_authenticated():
        return

    try:
        emails = gmail_service.fetch_unread_emails(max_results=10)
        if not emails:
            return

        async with AsyncSessionLocal() as db:
            for email_data in emails:
                email_id = email_data["id"]
                
                # Check if already processed
                existing = await db.get(ProcessingRecord, email_id)
                if existing:
                    # Already processed, make sure it's read so we don't fetch it again
                    gmail_service.mark_as_read(email_id, email_data.get("_imap_uid"))
                    continue
                
                logger.info(f"Background polling: processing new IMAP email {email_id}")
                
                # Remove _imap_uid before validating with pydantic
                imap_uid = email_data.pop("_imap_uid", None)
                incoming = IncomingEmail(**email_data)
                
                # Save to EmailRecord table so it persists in the UI
                existing_email = await db.get(EmailRecord, incoming.id)
                if not existing_email:
                    email_record = EmailRecord(**incoming.model_dump())
                    db.add(email_record)
                    await db.commit()
                
                try:
                    result = await process_email(incoming, db)
                    
                    # Pipeline may have re-routed business_id — update EmailRecord so it's persisted correctly
                    actual_business_id = incoming.business_id or "biz_tech"
                    if existing_email:
                        existing_email.business_id = actual_business_id
                    else:
                        # Re-fetch and update (it was added before pipeline ran)
                        email_rec_stored = await db.get(EmailRecord, incoming.id)
                        if email_rec_stored:
                            email_rec_stored.business_id = actual_business_id

                    # Persist record
                    record_data = result.model_dump_json()
                    
                    # Mark as read so we don't fetch it again
                    gmail_service.mark_as_read(incoming.id, imap_uid)
                    
                    record = ProcessingRecord(
                        email_id=incoming.id,
                        business_id=actual_business_id,
                        action=result.action.value,
                        order_id=result.order.id if result.order else "",
                        result_json=record_data,
                    )
                    
                    # Create draft OR send immediately
                    result_data = json.loads(record_data)
                    action_val = result.action.value
                    
                    if action_val == "escalate":
                        record.status = "pending"
                        gmail_service.create_gmail_draft(
                            to_email=incoming.from_email,
                            subject=incoming.subject,
                            html_body=result_data.get("drafted_reply_html", ""),
                            message_id=incoming.id,
                        )
                    else:
                        record.status = "resolved"
                        gmail_service.send_email(
                            to_email=incoming.from_email,
                            subject=incoming.subject,
                            html_body=result_data.get("drafted_reply_html", ""),
                            message_id=incoming.id,
                        )
                        
                    db.add(record)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to process polled email {email_id}: {e}")
                    await telegram_service.notify_error(str(e), "Email skipped, marked as error")
                    continue
                    
                # ── Fire Telegram Notifications ───────────────────────────────
                try:
                    action_val = result.action.value
                    customer = incoming.from_name

                    if action_val == "escalate":
                        # Send escalation approval request
                        await telegram_service.notify_escalation(
                            email_id=incoming.id,
                            email_subject=incoming.subject,
                            customer_name=incoming.from_name,
                            customer_email=incoming.from_email,
                            draft_reply=result.drafted_reply_text or "",
                            reason=result.escalation_reason or "Requires human judgment",
                            dossier=result.escalation_dossier,
                            audit_score=result.audit_score,
                            action_log_len=len(result.action_log)
                        )
                    else:
                        await telegram_service.notify_email_processed(
                            email_subject=incoming.subject,
                            action=action_val,
                            customer=customer,
                            sent_reply=result.drafted_reply_text or "",
                            audit_score=result.audit_score,
                            action_log_len=len(result.action_log)
                        )

                    # Invoice notification
                    if result.attachment_paths:
                        for path in result.attachment_paths:
                            if ".pdf" in path.lower() or "invoice" in path.lower():
                                order_id = result.order.id if result.order else "N/A"
                                amount = f"${result.order.amount:.2f}" if result.order else "N/A"
                                await telegram_service.notify_invoice(
                                    customer=incoming.from_name,
                                    issue=incoming.subject,
                                    invoice_id=order_id,
                                    amount=amount
                                )
                except Exception as tg_err:
                    logger.warning(f"Telegram notification failed (non-fatal): {tg_err}")
                    
    except Exception as e:
        logger.error(f"Error during Gmail poll iteration: {e}")

async def start_polling_loop():
    logger.info("Starting background Gmail polling loop (30s interval)")
    while True:
        await _poll_iteration()
        await asyncio.sleep(30)

async def trigger_manual_poll():
    logger.info("Manual Gmail poll triggered")
    await _poll_iteration()
