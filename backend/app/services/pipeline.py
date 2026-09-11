"""
Pipeline — orchestrates Phases 2–5 for each incoming email.
Steps: OCR → Extract → Match Order → RAG → Decide → Execute → Draft Reply
"""
import base64
import json
from datetime import datetime
from typing import Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.schemas import (
    IncomingEmail, ProcessingResult, ExtractedInvoiceData,
    ActionLogEntry, ResolutionAction
)
from app.services.ocr_service import extract_text_from_image
from app.services.llm_service import GeminiLLMService
from app.services.order_service import get_order, find_orders_for_customer
from app.services.ledger_service import append_event
from app.services.rag_service import RAGService
from app.services import action_service
from app.services.reply_service import draft_reply


def _log(step: str, description: str, detail: Optional[str] = None) -> ActionLogEntry:
    return ActionLogEntry(
        timestamp=datetime.utcnow(),
        step=step,
        description=description,
        detail=detail,
    )


async def process_email(email: IncomingEmail, db: AsyncSession) -> ProcessingResult:
    """Full AI pipeline. Never raises — escalates gracefully on any error."""
    log: list[ActionLogEntry] = []
    llm = GeminiLLMService.get_instance()
    rag = RAGService.get_instance()
    
    # ── Phase 1.5: Dynamic Routing (Determine business_id) ────────────────────
    business_id = email.business_id if getattr(email, "business_id", None) else "biz_tech"
    # Overwrite if we detect it's from another business via order lookup
    matched_any_order = await find_orders_for_customer(db, email.from_email, email.from_name, business_id=None)
    if matched_any_order:
        business_id = matched_any_order[0].business_id
        logger.info(f"Routed email to {business_id} based on existing order history.")
    else:
        # Fast LLM classification fallback
        classification_prompt = f"Does this email sound like it belongs to 'TechGadgets Inc.' (electronics, gadgets, chargers) or 'StyleBoutique' (clothing, apparel, dresses)? Reply ONLY with 'biz_tech' or 'biz_apparel'. Email: {email.subject} - {email.body[:300]}"
        try:
            detected = await llm._generate(classification_prompt)
            if "biz_apparel" in detected.lower():
                business_id = "biz_apparel"
            else:
                business_id = "biz_tech"
            logger.info(f"Routed email to {business_id} via LLM classification.")
        except:
            business_id = "biz_tech"
    
    email.business_id = business_id
    case_id = email.id

    # ── Phase 2 Ledger: Intake Event ──────────────────────────────────────────
    await append_event(db, business_id, case_id, "EMAIL_RECEIVED", {
        "from_name": email.from_name,
        "from_email": email.from_email,
        "subject": email.subject,
        "body_preview": email.body[:150],
        "attachment": email.attachment_filename,
    })

    extracted = ExtractedInvoiceData(raw_ocr_text="")
    order = None
    action_result = None
    order_id_hint: Optional[str] = None

    # ── Step 1: OCR ──────────────────────────────────────────────────────────
    if email.attachment_filename:
        image_data: Optional[bytes] = None
        if email.attachment_base64:
            try:
                image_data = base64.b64decode(email.attachment_base64)
            except Exception:
                pass

        from pathlib import Path as _Path
        attachments_dir = str(_Path(settings.POLICY_DOC_PATH).resolve().parent.parent / "attachments")
        raw_text, confidence = await extract_text_from_image(
            image_data=image_data,
            filename=email.attachment_filename,
            attachments_dir=attachments_dir,
        )
        extracted.raw_ocr_text = raw_text
        extracted.extraction_confidence = confidence

        if raw_text:
            log.append(_log("ocr", f"Read {len(raw_text)} characters from attachment '{email.attachment_filename}'",
                            detail=raw_text[:200] + "..." if len(raw_text) > 200 else raw_text))
        else:
            log.append(_log("ocr", f"Could not read text from '{email.attachment_filename}' — will analyse email body only"))
    else:
        log.append(_log("ocr", "No attachment — analysing email body text directly"))

    # ── Step 2: LLM Extraction ───────────────────────────────────────────────
    if extracted.raw_ocr_text:
        try:
            ext = await llm.extract_invoice_data(extracted.raw_ocr_text)
            extracted.order_id = ext.get("order_id")
            extracted.item     = ext.get("item")
            extracted.amount   = ext.get("amount")
            order_id_hint = extracted.order_id
            log.append(_log("ocr",
                f"Extracted from receipt: Order {extracted.order_id or '?'}, "
                f"Item: {extracted.item or '?'}, Amount: ${extracted.amount or '?'}",
                detail=json.dumps(ext)
            ))
        except Exception as e:
            log.append(_log("ocr", f"Could not extract structured data from attachment: {e}"))

    # Try to find order ID in email body if not found in attachment
    if not order_id_hint:
        import re
        m = re.search(r"ORD-\d+", email.body + " " + email.subject, re.IGNORECASE)
        if m:
            order_id_hint = m.group(0).upper()
            log.append(_log("match", f"Found order reference in email text: {order_id_hint}"))

    # ── Step 3: Order Matching (Business Scoped) ──────────────────────────────
    if order_id_hint:
        try:
            order = await get_order(db, order_id_hint, business_id)
            if order:
                log.append(_log("match",
                    f"Matched to order {order.id} — '{order.item}' for ${order.amount:.2f} "
                    f"({order.status}), customer: {order.customer_name}",
                    detail=f"Ordered by: {order.customer_email}"
                ))
            else:
                log.append(_log("match", f"Order '{order_id_hint}' not found in {business_id} system"))
        except Exception as e:
            log.append(_log("match", f"Order lookup failed: {e}"))

    # Fallback smart customer search (scoped to business_id)
    if not order:
        try:
            matched_orders = await find_orders_for_customer(db, email.from_email, email.from_name, business_id=business_id)
            if matched_orders:
                order = matched_orders[0]
                count_info = f" (1 of {len(matched_orders)} orders found)" if len(matched_orders) > 1 else ""
                log.append(_log("match",
                    f"Matched customer '{order.customer_name}' to order {order.id}{count_info} — '{order.item}' for ${order.amount:.2f} ({order.status})",
                    detail=f"Matched via customer lookup: {email.from_name} <{email.from_email}>"
                ))
            else:
                log.append(_log("match", f"No order found in {business_id} system matching ID '{order_id_hint or 'None'}' or customer '{email.from_name}'"))
        except Exception as e:
            log.append(_log("match", f"Smart customer order lookup failed: {e}"))

    # ── Step 4: RAG Policy Lookup (Business Scoped) ───────────────────────────
    query = f"{email.subject} {email.body[:300]}"
    try:
        policy_context = await rag.query(query, business_id=business_id)
        log.append(_log("decision", f"Pulled policy sections for business '{business_id}'"))
        await append_event(db, business_id, case_id, "POLICY_SEARCH", {
            "query": query,
            "policy_excerpt_preview": policy_context[:200]
        })
    except Exception as e:
        policy_context = "Policy unavailable — apply conservative defaults."
        log.append(_log("decision", f"Policy lookup failed: {e}"))

    # ── Step 5: Decision Engine ───────────────────────────────────────────────
    order_dict = None
    if order:
        order_dict = {
            "id": order.id, "item": order.item, "amount": order.amount,
            "status": order.status, "customer": order.customer_name,
            "business_id": getattr(order, "business_id", business_id)
        }
    try:
        decision = await llm.decide_action(
            email_body=email.body,
            order=order_dict,
            policy_context=policy_context,
        )
        chosen_action = decision.get("action", "escalate")
        reasoning = decision.get("reasoning", "Automated decision")
        log.append(_log("decision", f"Primary LLM Decision: {chosen_action.upper()} — {reasoning}"))
        await append_event(db, business_id, case_id, "LLM_DECISION", {
            "proposed_action": chosen_action,
            "reasoning": reasoning
        })
    except Exception as e:
        chosen_action = "escalate"
        reasoning = f"Decision engine error: {e}"
        log.append(_log("decision", f"Could not determine action, escalating: {e}"))

    # ── Phase 3: Auditor / Critic Agent Pre-Execution Audit ───────────────────
    audit_res = {"verdict": "AGREE", "risk_score": 10, "reasons": ["Standard resolution compliant with policy"], "flags": []}
    if chosen_action != "escalate":
        try:
            audit_res = await llm.audit_decision(
                primary_action=chosen_action,
                primary_reasoning=reasoning,
                email_body=email.body,
                ocr_text=extracted.raw_ocr_text,
                attachment_filename=email.attachment_filename,
                order=order_dict,
                policy_context=policy_context,
                customer_history_claims_count=0
            )
            log.append(_log("decision",
                f"Auditor Critic Verdict: {audit_res.get('verdict')} (Risk Score: {audit_res.get('risk_score')}/100)",
                detail="; ".join(audit_res.get("reasons", []))
            ))
            await append_event(db, business_id, case_id, "AUDITOR_VERDICT", audit_res)

            if audit_res.get("verdict") == "VETO" or audit_res.get("risk_score", 0) > 40:
                veto_reasons = "; ".join(audit_res.get("reasons", ["Risk flags detected"]))
                reasoning = f"Auditor VETO ({veto_reasons})"
                chosen_action = "escalate"
                log.append(_log("decision", f"Auditor VETO triggered — forced resolution to ESCALATE: {reasoning}"))
        except Exception as e:
            logger.warning(f"Auditor audit call failed: {e}")

    # Validate action string
    valid_actions = {"refund", "replace", "reissue_invoice", "issue_credit", "request_info", "answer_query", "escalate"}
    if chosen_action not in valid_actions:
        chosen_action = "escalate"

    # ── Step 6: Execute Action ────────────────────────────────────────────────
    corrected_amount = None
    if extracted.amount and order and abs(extracted.amount - order.amount) > 0.5:
        corrected_amount = order.amount

    try:
        if chosen_action == "refund" and order:
            action_result = await action_service.do_refund(db, order)
        elif chosen_action == "replace" and order:
            action_result = await action_service.do_replace(db, order)
        elif chosen_action == "reissue_invoice" and order:
            action_result = await action_service.do_reissue_invoice(db, order, corrected_amount)
        elif chosen_action == "issue_credit" and order:
            action_result = await action_service.do_issue_credit(db, order)
        elif chosen_action == "request_info":
            action_result = await action_service.do_request_info(db, order)
        elif chosen_action == "answer_query":
            action_result = await action_service.do_answer_query(db, order)
        else:
            escalation_reason = reasoning if chosen_action == "escalate" else "Order not found or action requires human review"
            action_result = await action_service.do_escalate(db, order, escalation_reason)
            chosen_action = "escalate"

        confirmation_id = action_result.get("confirmation_id")
        log.append(_log("action", action_result["description"], detail=f"Confirmation ID: {confirmation_id or 'N/A'}"))
        
        await append_event(db, business_id, case_id, "ACTION_EXECUTED", {
            "action": chosen_action,
            "description": action_result["description"],
            "confirmation_id": confirmation_id,
            "order_status": action_result.get("order_status")
        })

    except Exception as e:
        action_result = await action_service.do_escalate(db, order, f"Action execution failed: {e}")
        chosen_action = "escalate"
        log.append(_log("action", f"Could not execute action, escalated: {e}"))

    # ── Step 7: Draft Reply & Build Escalation Dossier ────────────────────────
    now = datetime.utcnow()
    reference_id = f"{order.id}-{now.strftime('%H%M')}" if order else f"CASE-{now.strftime('%y%m%d-%H%M')}"
    
    attachment_paths = []
    if action_result and action_result.get("pdf_path"):
        attachment_paths.append(action_result["pdf_path"])

    try:
        html_reply, text_reply, _ = await draft_reply(
            action=chosen_action,
            order=order,
            customer_name=email.from_name,
            customer_email=email.from_email,
            original_email_body=email.body,
            action_summary=action_result["description"],
            llm=llm,
            reference_id=reference_id,
            attachment_paths=attachment_paths,
            business_id=business_id,
        )
        log.append(_log("reply", "Drafted customer reply email — ready for approval"))
    except Exception as e:
        html_reply = f"<p>Dear {email.from_name},<br>{action_result['description']}<br>Reference ID: {reference_id}<br>Kind regards, SupportAI</p>"
        text_reply = f"Dear {email.from_name},\n\n{action_result['description']}\nReference ID: {reference_id}\n\nKind regards,\nSupportAI"

    # ── Phase 5: Escalation Dossier ───────────────────────────────────────────
    escalation_dossier = None
    if chosen_action == "escalate":
        recommended_action = "refund" if "refund" in email.body.lower() else "replace" if "replace" in email.body.lower() else "escalate"
        escalation_dossier = {
            "customer_email": email.from_email,
            "customer_name": email.from_name,
            "sentiment": "Frustrated / Urgent" if any(w in email.body.lower() for w in ["broken", "damaged", "refund", "where"]) else "Neutral",
            "primary_reason": reasoning,
            "auditor_flags": audit_res.get("flags", []),
            "auditor_reasons": audit_res.get("reasons", []),
            "policy_excerpt": policy_context[:300] + "...",
            "recommended_human_action": recommended_action,
            "recommended_action_description": f"Approve {recommended_action.upper()} for order {order.id if order else 'N/A'}",
        }

    # ── Build result ──────────────────────────────────────────────────────────
    from app.models.schemas import OrderSchema
    order_schema = OrderSchema.model_validate(order) if order else None

    return ProcessingResult(
        email_id=email.id,
        action=ResolutionAction(chosen_action),
        order=order_schema,
        extracted=extracted,
        reference_id=reference_id,
        drafted_reply_html=html_reply,
        drafted_reply_text=text_reply,
        action_log=log,
        attachment_paths=attachment_paths,
        escalation_reason=reasoning if chosen_action == "escalate" else None,
        audit_score=audit_res.get("risk_score", 10),
        audit_status=audit_res.get("verdict", "PASS"),
        escalation_dossier=escalation_dossier,
    )

